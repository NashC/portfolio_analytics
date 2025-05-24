"""
Portfolio Valuation Module (AP-4)

This module provides portfolio valuation functions that use the position_daily
and price_data tables for efficient, vectorized portfolio value calculations.
"""

from datetime import date, datetime
from typing import Optional, List, Union
import pandas as pd
import numpy as np
from sqlalchemy import select, and_
from sqlalchemy.orm import Session

from app.db.base import PositionDaily, PriceData, Asset, Account
from app.db.session import get_db


def get_portfolio_value(target_date: Union[date, datetime], 
                       account_ids: Optional[List[int]] = None) -> float:
    """
    Get the total portfolio value for a specific date.
    
    Args:
        target_date: Date to calculate portfolio value for
        account_ids: Optional list of account IDs to filter by
        
    Returns:
        Total portfolio value as float
    """
    if isinstance(target_date, datetime):
        target_date = target_date.date()
        
    with next(get_db()) as db:
        # Build query for positions on target date
        query = (
            select(
                PositionDaily.asset_id,
                PositionDaily.quantity,
                PriceData.close.label('price'),
                Asset.symbol
            )
            .join(PriceData, and_(
                PriceData.asset_id == PositionDaily.asset_id,
                PriceData.date == PositionDaily.date
            ))
            .join(Asset, Asset.asset_id == PositionDaily.asset_id)
            .where(PositionDaily.date == target_date)
        )
        
        if account_ids:
            query = query.where(PositionDaily.account_id.in_(account_ids))
            
        # Execute query and calculate total value
        results = db.execute(query).all()
        
        total_value = 0.0
        for row in results:
            # Handle stablecoins (assume price = 1.0 if no price data)
            price = row.price if row.price is not None else (
                1.0 if row.symbol.upper() in ['USDC', 'USDT', 'DAI', 'BUSD', 'GUSD'] else 0.0
            )
            # Ensure both quantity and price are converted to float
            total_value += float(row.quantity) * float(price)
            
        return float(total_value)


def get_value_series(start_date: Union[date, datetime], 
                    end_date: Union[date, datetime],
                    account_ids: Optional[List[int]] = None) -> pd.Series:
    """
    Get portfolio value time series using vectorized operations.
    
    Args:
        start_date: Start date for the series
        end_date: End date for the series
        account_ids: Optional list of account IDs to filter by
        
    Returns:
        pandas Series with UTC datetime index and portfolio values
    """
    if isinstance(start_date, datetime):
        start_date = start_date.date()
    if isinstance(end_date, datetime):
        end_date = end_date.date()
        
    with next(get_db()) as db:
        # Vectorized query to get all positions and prices in date range
        query = (
            select(
                PositionDaily.date,
                PositionDaily.asset_id,
                PositionDaily.quantity,
                PriceData.close.label('price'),
                Asset.symbol
            )
            .join(PriceData, and_(
                PriceData.asset_id == PositionDaily.asset_id,
                PriceData.date == PositionDaily.date
            ))
            .join(Asset, Asset.asset_id == PositionDaily.asset_id)
            .where(and_(
                PositionDaily.date >= start_date,
                PositionDaily.date <= end_date
            ))
        )
        
        if account_ids:
            query = query.where(PositionDaily.account_id.in_(account_ids))
            
        # Execute query and convert to DataFrame
        results = db.execute(query).all()
        
        if not results:
            # Return empty series with proper index
            date_range = pd.date_range(start=start_date, end=end_date, freq='D', tz='UTC')
            return pd.Series(0.0, index=date_range, name='portfolio_value')
        
        # Convert to DataFrame for vectorized operations
        df = pd.DataFrame(results, columns=['date', 'asset_id', 'quantity', 'price', 'symbol'])
        
        # Handle stablecoins - set price to 1.0 if missing
        stablecoins = ['USDC', 'USDT', 'DAI', 'BUSD', 'GUSD']
        stablecoin_mask = df['symbol'].str.upper().isin(stablecoins)
        df.loc[stablecoin_mask & df['price'].isna(), 'price'] = 1.0
        
        # Fill remaining NaN prices with 0 (will result in 0 value)
        df['price'] = df['price'].fillna(0.0)
        
        # Calculate value for each position
        df['value'] = df['quantity'].astype(float) * df['price'].astype(float)
        
        # Group by date and sum values
        daily_values = df.groupby('date')['value'].sum()
        
        # Create complete date range and reindex
        date_range = pd.date_range(start=start_date, end=end_date, freq='D')
        daily_values = daily_values.reindex(date_range, fill_value=0.0)
        
        # Ensure all values are float type
        daily_values = daily_values.astype(float)
        
        # Convert to UTC timezone as required
        daily_values.index = pd.to_datetime(daily_values.index).tz_localize('UTC')
        daily_values.name = 'portfolio_value'
        
        return daily_values


def get_asset_values_series(start_date: Union[date, datetime], 
                           end_date: Union[date, datetime],
                           account_ids: Optional[List[int]] = None) -> pd.DataFrame:
    """
    Get portfolio value time series broken down by asset.
    
    Args:
        start_date: Start date for the series
        end_date: End date for the series
        account_ids: Optional list of account IDs to filter by
        
    Returns:
        pandas DataFrame with UTC datetime index and asset value columns
    """
    if isinstance(start_date, datetime):
        start_date = start_date.date()
    if isinstance(end_date, datetime):
        end_date = end_date.date()
        
    with next(get_db()) as db:
        # Vectorized query to get all positions and prices in date range
        query = (
            select(
                PositionDaily.date,
                PositionDaily.asset_id,
                PositionDaily.quantity,
                PriceData.close.label('price'),
                Asset.symbol
            )
            .join(PriceData, and_(
                PriceData.asset_id == PositionDaily.asset_id,
                PriceData.date == PositionDaily.date
            ))
            .join(Asset, Asset.asset_id == PositionDaily.asset_id)
            .where(and_(
                PositionDaily.date >= start_date,
                PositionDaily.date <= end_date
            ))
        )
        
        if account_ids:
            query = query.where(PositionDaily.account_id.in_(account_ids))
            
        # Execute query and convert to DataFrame
        results = db.execute(query).all()
        
        if not results:
            # Return empty DataFrame with proper index
            date_range = pd.date_range(start=start_date, end=end_date, freq='D', tz='UTC')
            return pd.DataFrame(index=date_range)
        
        # Convert to DataFrame for vectorized operations
        df = pd.DataFrame(results, columns=['date', 'asset_id', 'quantity', 'price', 'symbol'])
        
        # Handle stablecoins - set price to 1.0 if missing
        stablecoins = ['USDC', 'USDT', 'DAI', 'BUSD', 'GUSD']
        stablecoin_mask = df['symbol'].str.upper().isin(stablecoins)
        df.loc[stablecoin_mask & df['price'].isna(), 'price'] = 1.0
        
        # Fill remaining NaN prices with 0 (will result in 0 value)
        df['price'] = df['price'].fillna(0.0)
        
        # Calculate value for each position
        df['value'] = df['quantity'] * df['price']
        
        # Pivot to get assets as columns
        asset_values = df.pivot_table(
            index='date', 
            columns='symbol', 
            values='value', 
            aggfunc='sum',
            fill_value=0.0
        )
        
        # Create complete date range and reindex
        date_range = pd.date_range(start=start_date, end=end_date, freq='D')
        asset_values = asset_values.reindex(date_range, fill_value=0.0)
        
        # Convert to UTC timezone as required
        asset_values.index = pd.to_datetime(asset_values.index).tz_localize('UTC')
        
        return asset_values


def validate_valuation_accuracy(start_date: Union[date, datetime], 
                               end_date: Union[date, datetime],
                               tolerance: float = 0.01) -> dict:
    """
    Validate portfolio valuation accuracy by comparing with manual calculations.
    
    Args:
        start_date: Start date for validation
        end_date: End date for validation
        tolerance: Acceptable difference percentage (default 0.01 = 1%)
        
    Returns:
        Dictionary with validation results
    """
    if isinstance(start_date, datetime):
        start_date = start_date.date()
    if isinstance(end_date, datetime):
        end_date = end_date.date()
        
    # Get portfolio value series
    value_series = get_value_series(start_date, end_date)
    
    # Sample a few dates for manual validation
    sample_dates = pd.date_range(start=start_date, end=end_date, freq='7D')[:5]
    
    validation_results = {
        'total_dates_checked': len(sample_dates),
        'passed': 0,
        'failed': 0,
        'tolerance': tolerance,
        'details': []
    }
    
    for sample_date in sample_dates:
        if sample_date.date() > end_date:
            continue
            
        # Get automated value
        auto_value = value_series.get(sample_date, 0.0)
        
        # Get manual calculation
        manual_value = get_portfolio_value(sample_date.date())
        
        # Calculate difference
        if manual_value > 0:
            diff_pct = abs(auto_value - manual_value) / manual_value
        else:
            diff_pct = 0.0 if auto_value == 0 else 1.0
            
        passed = diff_pct <= tolerance
        
        validation_results['details'].append({
            'date': sample_date.date(),
            'automated_value': auto_value,
            'manual_value': manual_value,
            'difference_pct': diff_pct,
            'passed': passed
        })
        
        if passed:
            validation_results['passed'] += 1
        else:
            validation_results['failed'] += 1
    
    validation_results['success_rate'] = (
        validation_results['passed'] / validation_results['total_dates_checked']
        if validation_results['total_dates_checked'] > 0 else 0.0
    )
    
    return validation_results 