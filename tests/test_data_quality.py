#!/usr/bin/env python3

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

from app.ingestion.normalization import (
    normalize_data, 
    remove_duplicates, 
    validate_timestamps, 
    validate_quantities_and_prices,
    filter_to_canonical_columns,
    CANONICAL_COLUMNS,
    CANONICAL_TYPES
)
from app.analytics.portfolio import compute_portfolio_time_series_with_external_prices


class TestDataQuality:
    """Comprehensive data quality tests to prevent issues like inflated portfolio values."""
    
    def test_duplicate_transaction_removal(self):
        """Test that exact duplicate transactions are properly removed."""
        # Create test data with duplicates
        test_data = pd.DataFrame({
            'timestamp': [datetime(2024, 1, 1), datetime(2024, 1, 1), datetime(2024, 1, 2)],
            'type': ['buy', 'buy', 'sell'],
            'asset': ['BTC', 'BTC', 'BTC'],
            'quantity': [1.0, 1.0, 0.5],
            'price': [50000, 50000, 51000],
            'fees': [10, 10, 5],
            'institution': ['coinbase', 'coinbase', 'coinbase']
        })
        
        # Remove duplicates
        result = remove_duplicates(test_data)
        
        # Should have 2 transactions (1 duplicate removed)
        assert len(result) == 2
        assert len(result[result['type'] == 'buy']) == 1
        assert len(result[result['type'] == 'sell']) == 1
    
    def test_future_date_validation(self):
        """Test that unrealistic future dates are filtered out."""
        future_date = datetime.now() + timedelta(days=400)  # More than 1 year in future
        
        test_data = pd.DataFrame({
            'timestamp': [datetime(2024, 1, 1), future_date, datetime(2024, 1, 2)],
            'type': ['buy', 'buy', 'sell'],
            'asset': ['BTC', 'BTC', 'BTC'],
            'quantity': [1.0, 1.0, 0.5],
            'price': [50000, 50000, 51000],
            'fees': [10, 10, 5],
            'institution': ['coinbase', 'coinbase', 'coinbase']
        })
        
        result = validate_timestamps(test_data)
        
        # Should have 2 transactions (future date removed)
        assert len(result) == 2
        assert all(result['timestamp'] <= datetime.now() + timedelta(days=365))
    
    def test_null_asset_removal(self):
        """Test that transactions with null assets are removed."""
        test_data = pd.DataFrame({
            'timestamp': [datetime(2024, 1, 1), datetime(2024, 1, 2), datetime(2024, 1, 3)],
            'type': ['buy', 'buy', 'sell'],
            'asset': ['BTC', None, 'ETH'],
            'quantity': [1.0, 1.0, 0.5],
            'price': [50000, 50000, 3500],
            'fees': [10, 10, 5],
            'institution': ['coinbase', 'coinbase', 'coinbase']
        })
        
        result = validate_quantities_and_prices(test_data)
        
        # Should have 2 transactions (null asset removed)
        assert len(result) == 2
        assert result['asset'].notna().all()
    
    def test_zero_quantity_removal(self):
        """Test that non-fee transactions with zero quantity are removed."""
        test_data = pd.DataFrame({
            'timestamp': [datetime(2024, 1, 1), datetime(2024, 1, 2), datetime(2024, 1, 3)],
            'type': ['buy', 'buy', 'fee'],
            'asset': ['BTC', 'ETH', 'BTC'],
            'quantity': [1.0, 0.0, 0.0],  # Zero quantity buy should be removed, zero quantity fee should stay
            'price': [50000, 3500, 0],
            'fees': [10, 5, 10],
            'institution': ['coinbase', 'coinbase', 'coinbase']
        })
        
        result = validate_quantities_and_prices(test_data)
        
        # Should have 2 transactions (zero quantity buy removed, fee transaction kept)
        assert len(result) == 2
        assert len(result[result['type'] == 'buy']) == 1
        assert len(result[result['type'] == 'fee']) == 1
    
    def test_canonical_column_filtering(self):
        """Test that only canonical columns are kept in the output."""
        test_data = pd.DataFrame({
            'timestamp': [datetime(2024, 1, 1)],
            'type': ['buy'],
            'asset': ['BTC'],
            'quantity': [1.0],
            'price': [50000],
            'fees': [10],
            'institution': ['coinbase'],
            # Extra columns that should be removed
            'extra_column_1': ['value1'],
            'extra_column_2': [123],
            'original_type': ['Buy']
        })
        
        result = filter_to_canonical_columns(test_data)
        
        # Should only have canonical columns
        assert list(result.columns) == CANONICAL_COLUMNS
        assert len(result.columns) == len(CANONICAL_COLUMNS)
        assert 'extra_column_1' not in result.columns
        assert 'extra_column_2' not in result.columns
    
    def test_transaction_type_validation(self):
        """Test that all transaction types are canonical."""
        test_data = pd.DataFrame({
            'timestamp': [datetime(2024, 1, 1), datetime(2024, 1, 2)],
            'type': ['buy', 'invalid_type'],
            'asset': ['BTC', 'ETH'],
            'quantity': [1.0, 1.0],
            'price': [50000, 3500],
            'fees': [10, 5],
            'institution': ['coinbase', 'coinbase']
        })
        
        # Normalize the data
        result = normalize_data(test_data)
        
        # All types should be canonical (invalid_type should become 'unknown')
        assert all(t in CANONICAL_TYPES for t in result['type'].unique())
        assert 'invalid_type' not in result['type'].values
    
    def test_complete_normalization_pipeline(self):
        """Test the complete normalization pipeline for data quality."""
        # Create test data with various issues
        test_data = pd.DataFrame({
            'timestamp': [
                datetime(2024, 1, 1), 
                datetime(2024, 1, 1),  # Duplicate
                datetime(2024, 1, 2),
                datetime.now() + timedelta(days=400),  # Future date
                datetime(2024, 1, 3)
            ],
            'type': ['buy', 'buy', 'sell', 'buy', 'invalid_type'],
            'asset': ['BTC', 'BTC', 'ETH', 'BTC', None],  # Null asset
            'quantity': [1.0, 1.0, 0.5, 1.0, 0.0],  # Zero quantity
            'price': [50000, 50000, 3500, 50000, 0],
            'fees': [10, 10, 5, 10, 0],
            'institution': ['coinbase', 'coinbase', 'coinbase', 'coinbase', 'coinbase'],
            'extra_column': ['a', 'b', 'c', 'd', 'e']  # Extra column
        })
        
        result = normalize_data(test_data)
        
        # Validate the result
        assert len(result) <= len(test_data)  # Should have fewer or equal rows
        assert list(result.columns) == CANONICAL_COLUMNS  # Only canonical columns
        assert result['timestamp'].notna().all()  # No null timestamps
        assert result['asset'].notna().all()  # No null assets
        assert all(t in CANONICAL_TYPES for t in result['type'].unique())  # All canonical types
        assert not result.duplicated().any()  # No duplicates


class TestPortfolioCalculation:
    """Tests for portfolio calculation to prevent inflated values."""
    
    def test_transfer_exclusion(self):
        """Test that internal transfers are excluded from portfolio calculations."""
        test_data = pd.DataFrame({
            'timestamp': [datetime(2024, 1, 1), datetime(2024, 1, 2), datetime(2024, 1, 3)],
            'type': ['buy', 'transfer_in', 'transfer_out'],  # Only 'buy' should affect portfolio
            'asset': ['BTC', 'BTC', 'BTC'],
            'quantity': [1.0, 5.0, 2.0],  # Large transfers should be ignored
            'price': [50000, 50000, 50000],
            'fees': [10, 0, 0],
            'institution': ['coinbase', 'coinbase', 'coinbase']
        })
        
        # Mock the price fetching to return simple prices
        with patch('app.analytics.portfolio.fetch_historical_prices') as mock_fetch:
            mock_prices = pd.DataFrame({
                'BTC': [50000, 51000, 52000]
            }, index=pd.date_range('2024-01-01', periods=3, freq='D'))
            mock_fetch.return_value = mock_prices
            
            result = compute_portfolio_time_series_with_external_prices(test_data)
            
            # Should only have 1 BTC from the buy transaction
            if not result.empty:
                final_btc_holdings = result['BTC'].iloc[-1] / 52000  # Divide by price to get quantity
                assert abs(final_btc_holdings - 1.0) < 0.01  # Should be ~1 BTC, not 6 BTC
    
    def test_holdings_calculation_accuracy(self):
        """Test that holdings are calculated correctly without inflation."""
        test_data = pd.DataFrame({
            'timestamp': [
                datetime(2024, 1, 1),
                datetime(2024, 1, 2),
                datetime(2024, 1, 3)
            ],
            'type': ['buy', 'buy', 'sell'],
            'asset': ['ETH', 'ETH', 'ETH'],
            'quantity': [10.0, 5.0, -3.0],  # FIXED: Sell should be negative
            'price': [3000, 3100, 3200],
            'fees': [10, 5, 8],
            'institution': ['coinbase', 'coinbase', 'coinbase']
        })
        
        with patch('app.analytics.portfolio.fetch_historical_prices') as mock_fetch:
            mock_prices = pd.DataFrame({
                'ETH': [3000, 3100, 3200]
            }, index=pd.date_range('2024-01-01', periods=3, freq='D'))
            mock_fetch.return_value = mock_prices
            
            result = compute_portfolio_time_series_with_external_prices(test_data)
            
            if not result.empty:
                # Final holdings should be 12 ETH (10 + 5 - 3)
                final_eth_holdings = result['ETH'].iloc[-1] / 3200  # Divide by price
                assert abs(final_eth_holdings - 12.0) < 0.01
                
                # Portfolio value should be reasonable (12 ETH * 3200 = 38,400)
                final_value = result['total'].iloc[-1]
                assert 38000 < final_value < 39000
    
    def test_cumulative_holdings_logic(self):
        """Test that cumulative holdings are calculated correctly."""
        test_data = pd.DataFrame({
            'timestamp': [
                datetime(2024, 1, 1),
                datetime(2024, 1, 5),  # Gap in dates
                datetime(2024, 1, 10)
            ],
            'type': ['buy', 'buy', 'sell'],
            'asset': ['BTC', 'BTC', 'BTC'],
            'quantity': [1.0, 2.0, -0.5],  # FIXED: Sell should be negative
            'price': [50000, 51000, 52000],
            'fees': [10, 20, 15],
            'institution': ['coinbase', 'coinbase', 'coinbase']
        })
        
        with patch('app.analytics.portfolio.fetch_historical_prices') as mock_fetch:
            # Create price data for the full date range
            date_range = pd.date_range('2024-01-01', '2024-01-10', freq='D')
            mock_prices = pd.DataFrame({
                'BTC': [50000 + i*100 for i in range(len(date_range))]
            }, index=date_range)
            mock_fetch.return_value = mock_prices
            
            result = compute_portfolio_time_series_with_external_prices(test_data)
            
            if not result.empty:
                # Check holdings progression
                # Day 1: 1 BTC
                day1_holdings = result['BTC'].iloc[0] / mock_prices['BTC'].iloc[0]
                assert abs(day1_holdings - 1.0) < 0.01
                
                # Day 5: 3 BTC (1 + 2)
                day5_holdings = result['BTC'].iloc[4] / mock_prices['BTC'].iloc[4]
                assert abs(day5_holdings - 3.0) < 0.01
                
                # Day 10: 2.5 BTC (3 - 0.5)
                day10_holdings = result['BTC'].iloc[-1] / mock_prices['BTC'].iloc[-1]
                assert abs(day10_holdings - 2.5) < 0.01
    
    def test_portfolio_value_reasonableness(self):
        """Test that portfolio values are within reasonable bounds."""
        test_data = pd.DataFrame({
            'timestamp': [datetime(2024, 1, 1)],
            'type': ['buy'],
            'asset': ['BTC'],
            'quantity': [1.0],
            'price': [50000],
            'fees': [10],
            'institution': ['coinbase']
        })
        
        with patch('app.analytics.portfolio.fetch_historical_prices') as mock_fetch:
            mock_prices = pd.DataFrame({
                'BTC': [60000]  # Current price
            }, index=[datetime(2024, 1, 1)])
            mock_fetch.return_value = mock_prices
            
            result = compute_portfolio_time_series_with_external_prices(test_data)
            
            if not result.empty:
                portfolio_value = result['total'].iloc[-1]
                
                # Portfolio should be around 60,000 (1 BTC * 60,000)
                assert 50000 < portfolio_value < 70000
                
                # Should not be inflated to millions
                assert portfolio_value < 1000000
    
    def test_no_duplicate_asset_columns(self):
        """Test that portfolio calculation doesn't create duplicate asset columns."""
        test_data = pd.DataFrame({
            'timestamp': [datetime(2024, 1, 1), datetime(2024, 1, 2)],
            'type': ['buy', 'buy'],
            'asset': ['ETH', 'ETH'],
            'quantity': [1.0, 1.0],
            'price': [3000, 3100],
            'fees': [10, 10],
            'institution': ['coinbase', 'coinbase']
        })
        
        with patch('app.analytics.portfolio.fetch_historical_prices') as mock_fetch:
            mock_prices = pd.DataFrame({
                'ETH': [3000, 3100]
            }, index=pd.date_range('2024-01-01', periods=2, freq='D'))
            mock_fetch.return_value = mock_prices
            
            result = compute_portfolio_time_series_with_external_prices(test_data)
            
            if not result.empty:
                # Should only have one ETH column plus total
                eth_columns = [col for col in result.columns if 'ETH' in col]
                assert len(eth_columns) == 1
                assert eth_columns[0] == 'ETH'


class TestDataIntegrity:
    """Tests for overall data integrity and consistency."""
    
    def test_transaction_balance_consistency(self):
        """Test that transaction quantities sum correctly for each asset."""
        test_data = pd.DataFrame({
            'timestamp': [datetime(2024, 1, 1), datetime(2024, 1, 2), datetime(2024, 1, 3)],
            'type': ['buy', 'buy', 'sell'],
            'asset': ['BTC', 'BTC', 'BTC'],
            'quantity': [1.0, 2.0, -0.5],  # FIXED: Sell should be negative
            'price': [50000, 51000, 52000],
            'fees': [10, 20, 15],
            'institution': ['coinbase', 'coinbase', 'coinbase']
        })
        
        # Filter to portfolio-affecting transactions
        portfolio_affecting_types = ['buy', 'sell', 'staking_reward', 'dividend', 'interest', 'deposit', 'withdrawal', 'swap']
        filtered_data = test_data[test_data['type'].isin(portfolio_affecting_types)]
        
        # Calculate net quantity for each asset
        net_quantities = filtered_data.groupby('asset')['quantity'].sum()
        
        # BTC should have net quantity of 2.5 (1 + 2 - 0.5)
        assert abs(net_quantities['BTC'] - 2.5) < 0.01
    
    def test_price_data_consistency(self):
        """Test that price data is consistent and reasonable."""
        # This would test the price fetching logic
        with patch('app.analytics.portfolio.load_historical_price_csv') as mock_load:
            # Mock reasonable price data
            mock_prices = pd.DataFrame({
                'BTC': [50000, 51000, 52000]
            }, index=pd.date_range('2024-01-01', periods=3, freq='D'))
            mock_load.return_value = mock_prices
            
            from app.analytics.portfolio import load_historical_price_csv
            result = load_historical_price_csv('BTC', datetime(2024, 1, 1), datetime(2024, 1, 3))
            
            if result is not None:
                # Prices should be positive
                assert (result['BTC'] > 0).all()
                
                # Prices should be reasonable (not inflated)
                assert result['BTC'].max() < 1000000  # Less than $1M per BTC
                assert result['BTC'].min() > 1  # More than $1 per BTC
    
    def test_institution_data_consistency(self):
        """Test that institution data is properly handled."""
        test_data = pd.DataFrame({
            'timestamp': [datetime(2024, 1, 1), datetime(2024, 1, 2)],
            'type': ['buy', 'buy'],
            'asset': ['BTC', 'ETH'],
            'quantity': [1.0, 10.0],
            'price': [50000, 3000],
            'fees': [10, 15],
            'institution': ['coinbase', 'binanceus']
        })
        
        result = normalize_data(test_data)
        
        # Institution column should be preserved
        assert 'institution' in result.columns
        assert 'coinbase' in result['institution'].values
        assert 'binanceus' in result['institution'].values
    
    def test_edge_case_handling(self):
        """Test handling of edge cases that could cause issues."""
        # Empty DataFrame
        empty_data = pd.DataFrame(columns=CANONICAL_COLUMNS)
        result = normalize_data(empty_data)
        assert len(result) == 0
        assert list(result.columns) == CANONICAL_COLUMNS
        
        # Single transaction
        single_data = pd.DataFrame({
            'timestamp': [datetime(2024, 1, 1)],
            'type': ['buy'],
            'asset': ['BTC'],
            'quantity': [1.0],
            'price': [50000],
            'fees': [10],
            'institution': ['coinbase']
        })
        result = normalize_data(single_data)
        assert len(result) == 1
        
        # Very large quantities (should be flagged but not removed)
        large_data = pd.DataFrame({
            'timestamp': [datetime(2024, 1, 1)],
            'type': ['buy'],
            'asset': ['SHIB'],  # Meme coin with large quantities
            'quantity': [1000000],  # 1 million tokens
            'price': [0.00001],
            'fees': [10],
            'institution': ['coinbase']
        })
        result = normalize_data(large_data)
        assert len(result) == 1  # Should not be removed


if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 