"""
Returns Calculation Library (AP-5)

This module provides functions for calculating portfolio returns, including:
- Daily returns
- Cumulative returns  
- Time-weighted rate of return (TWRR)

All functions include type hints and comprehensive docstrings.
"""

from typing import Union, List, Optional, Tuple
import pandas as pd
import numpy as np
from datetime import date, datetime


def daily_returns(series: pd.Series) -> pd.Series:
    """
    Calculate daily returns from a price or value series.
    
    Args:
        series: pandas Series with datetime index and numeric values
        
    Returns:
        pandas Series with daily percentage returns
        
    Raises:
        ValueError: If series is empty or contains non-numeric values
        
    Example:
        >>> prices = pd.Series([100, 102, 101, 105], 
        ...                   index=pd.date_range('2024-01-01', periods=4))
        >>> returns = daily_returns(prices)
        >>> returns.iloc[0]  # First return: (102-100)/100 = 0.02
        0.02
    """
    if series.empty:
        raise ValueError("Input series cannot be empty")
    
    if not pd.api.types.is_numeric_dtype(series):
        raise ValueError("Input series must contain numeric values")
    
    # Calculate percentage change and drop NaN values
    returns = series.pct_change().dropna()
    
    # Set name for the series
    returns.name = f"{series.name}_daily_returns" if series.name else "daily_returns"
    
    return returns


def cumulative_returns(series: pd.Series) -> pd.Series:
    """
    Calculate cumulative returns from a daily returns series.
    
    Args:
        series: pandas Series with daily returns (as decimals, not percentages)
        
    Returns:
        pandas Series with cumulative returns
        
    Raises:
        ValueError: If series is empty or contains non-numeric values
        
    Example:
        >>> daily_rets = pd.Series([0.02, -0.01, 0.04], 
        ...                       index=pd.date_range('2024-01-01', periods=3))
        >>> cum_rets = cumulative_returns(daily_rets)
        >>> cum_rets.iloc[-1]  # Final cumulative return
        0.0508
    """
    if series.empty:
        raise ValueError("Input series cannot be empty")
    
    if not pd.api.types.is_numeric_dtype(series):
        raise ValueError("Input series must contain numeric values")
    
    # Calculate cumulative returns: (1 + r1) * (1 + r2) * ... - 1
    cum_returns = (1 + series).cumprod() - 1
    
    # Set name for the series
    cum_returns.name = f"{series.name}_cumulative" if series.name else "cumulative_returns"
    
    return cum_returns


def twrr(series: pd.Series, cash_flows: Optional[pd.Series] = None) -> float:
    """
    Calculate Time-Weighted Rate of Return (TWRR).
    
    This method eliminates the impact of cash flows to measure the performance
    of the investment manager or strategy.
    
    Args:
        series: pandas Series with portfolio values over time
        cash_flows: Optional pandas Series with cash flows (positive for inflows,
                   negative for outflows). If None, assumes no cash flows.
        
    Returns:
        Annualized time-weighted rate of return as a decimal
        
    Raises:
        ValueError: If series is empty, contains non-numeric values, or has
                   insufficient data points
        
    Example:
        >>> values = pd.Series([1000, 1100, 1050, 1200], 
        ...                   index=pd.date_range('2024-01-01', periods=4))
        >>> twrr_result = twrr(values)
        >>> round(twrr_result, 4)  # Annualized TWRR
        0.2449
    """
    if series.empty:
        raise ValueError("Input series cannot be empty")
    
    if len(series) < 2:
        raise ValueError("Need at least 2 data points to calculate TWRR")
    
    if not pd.api.types.is_numeric_dtype(series):
        raise ValueError("Input series must contain numeric values")
    
    # If no cash flows provided, calculate simple geometric return
    if cash_flows is None:
        # Calculate daily returns and compound them
        daily_rets = daily_returns(series)
        if daily_rets.empty:
            return 0.0
        
        # Geometric mean of returns
        total_return = (1 + daily_rets).prod() - 1
        
        # Annualize based on time period
        days = (series.index[-1] - series.index[0]).days
        if days <= 0:
            return 0.0
        
        periods_per_year = 365.25 / days
        annualized_return = (1 + total_return) ** periods_per_year - 1
        
        return annualized_return
    
    # Handle cash flows case
    # Align cash flows with portfolio values
    aligned_flows = cash_flows.reindex(series.index, fill_value=0.0)
    
    # Calculate sub-period returns between cash flows
    sub_returns = []
    
    for i in range(1, len(series)):
        prev_value = series.iloc[i-1]
        curr_value = series.iloc[i]
        flow = aligned_flows.iloc[i]
        
        # Adjust for cash flow: return = (ending_value - cash_flow) / beginning_value - 1
        if prev_value != 0:
            sub_return = (curr_value - flow) / prev_value - 1
            sub_returns.append(sub_return)
    
    if not sub_returns:
        return 0.0
    
    # Compound the sub-period returns
    total_return = np.prod([1 + r for r in sub_returns]) - 1
    
    # Annualize
    days = (series.index[-1] - series.index[0]).days
    if days <= 0:
        return 0.0
    
    periods_per_year = 365.25 / days
    annualized_return = (1 + total_return) ** periods_per_year - 1
    
    return annualized_return


def rolling_returns(series: pd.Series, window: int) -> pd.Series:
    """
    Calculate rolling returns over a specified window.
    
    Args:
        series: pandas Series with portfolio values over time
        window: Number of periods for the rolling window
        
    Returns:
        pandas Series with rolling returns
        
    Raises:
        ValueError: If series is empty or window is invalid
        
    Example:
        >>> values = pd.Series([100, 102, 101, 105, 108], 
        ...                   index=pd.date_range('2024-01-01', periods=5))
        >>> rolling_rets = rolling_returns(values, window=3)
        >>> len(rolling_rets)  # Should have 3 values (5 - 3 + 1)
        3
    """
    if series.empty:
        raise ValueError("Input series cannot be empty")
    
    if window <= 0 or window > len(series):
        raise ValueError(f"Window must be between 1 and {len(series)}")
    
    # Calculate rolling returns
    rolling_rets = series.rolling(window=window).apply(
        lambda x: (x.iloc[-1] / x.iloc[0] - 1) if x.iloc[0] != 0 else 0.0
    ).dropna()
    
    rolling_rets.name = f"{series.name}_rolling_{window}d" if series.name else f"rolling_{window}d_returns"
    
    return rolling_rets


def volatility(returns: pd.Series, annualized: bool = True) -> float:
    """
    Calculate volatility (standard deviation) of returns.
    
    Args:
        returns: pandas Series with daily returns
        annualized: Whether to annualize the volatility (default True)
        
    Returns:
        Volatility as a decimal
        
    Raises:
        ValueError: If returns series is empty or contains non-numeric values
        
    Example:
        >>> daily_rets = pd.Series([0.01, -0.02, 0.015, -0.005])
        >>> vol = volatility(daily_rets, annualized=True)
        >>> vol > 0  # Should be positive
        True
    """
    if returns.empty:
        raise ValueError("Returns series cannot be empty")
    
    if not pd.api.types.is_numeric_dtype(returns):
        raise ValueError("Returns series must contain numeric values")
    
    vol = returns.std()
    
    if annualized:
        # Annualize assuming 252 trading days per year
        vol *= np.sqrt(252)
    
    return vol


def sharpe_ratio(returns: pd.Series, risk_free_rate: float = 0.02) -> float:
    """
    Calculate Sharpe ratio from returns series.
    
    Args:
        returns: pandas Series with daily returns
        risk_free_rate: Annual risk-free rate (default 2%)
        
    Returns:
        Sharpe ratio as a float
        
    Raises:
        ValueError: If returns series is empty or contains non-numeric values
        
    Example:
        >>> daily_rets = pd.Series([0.01, -0.02, 0.015, -0.005])
        >>> sr = sharpe_ratio(daily_rets, risk_free_rate=0.02)
        >>> isinstance(sr, float)
        True
    """
    if returns.empty:
        raise ValueError("Returns series cannot be empty")
    
    if not pd.api.types.is_numeric_dtype(returns):
        raise ValueError("Returns series must contain numeric values")
    
    # Convert annual risk-free rate to daily
    daily_rf = risk_free_rate / 252
    
    # Calculate excess returns
    excess_returns = returns - daily_rf
    
    # Calculate Sharpe ratio
    if excess_returns.std() == 0:
        return 0.0
    
    sharpe = excess_returns.mean() / excess_returns.std() * np.sqrt(252)
    
    return sharpe


def maximum_drawdown(series: pd.Series) -> Tuple[float, pd.Timestamp, pd.Timestamp]:
    """
    Calculate maximum drawdown from a price/value series.
    
    Args:
        series: pandas Series with portfolio values over time
        
    Returns:
        Tuple of (max_drawdown, peak_date, trough_date)
        
    Raises:
        ValueError: If series is empty or contains non-numeric values
        
    Example:
        >>> values = pd.Series([100, 110, 90, 95], 
        ...                   index=pd.date_range('2024-01-01', periods=4))
        >>> max_dd, peak, trough = maximum_drawdown(values)
        >>> max_dd  # Should be around -0.18 (90/110 - 1)
        -0.18181818181818182
    """
    if series.empty:
        raise ValueError("Input series cannot be empty")
    
    if not pd.api.types.is_numeric_dtype(series):
        raise ValueError("Input series must contain numeric values")
    
    # Calculate running maximum (peak)
    peak_values = series.expanding().max()
    
    # Calculate drawdowns
    drawdowns = series / peak_values - 1
    
    # Find maximum drawdown
    max_dd = drawdowns.min()
    max_dd_date = drawdowns.idxmin()
    
    # Find the peak date (last peak before the maximum drawdown)
    peak_date = peak_values.loc[:max_dd_date].idxmax()
    
    return max_dd, peak_date, max_dd_date


def calmar_ratio(returns: pd.Series, max_dd: Optional[float] = None) -> float:
    """
    Calculate Calmar ratio (annualized return / maximum drawdown).
    
    Args:
        returns: pandas Series with daily returns
        max_dd: Optional pre-calculated maximum drawdown. If None, will be calculated.
        
    Returns:
        Calmar ratio as a float
        
    Raises:
        ValueError: If returns series is empty or contains non-numeric values
        
    Example:
        >>> daily_rets = pd.Series([0.01, -0.02, 0.015, -0.005])
        >>> calmar = calmar_ratio(daily_rets)
        >>> isinstance(calmar, float)
        True
    """
    if returns.empty:
        raise ValueError("Returns series cannot be empty")
    
    if not pd.api.types.is_numeric_dtype(returns):
        raise ValueError("Returns series must contain numeric values")
    
    # Calculate annualized return
    annualized_return = returns.mean() * 252
    
    # Calculate maximum drawdown if not provided
    if max_dd is None:
        # Convert returns to cumulative values to calculate drawdown
        cum_values = (1 + returns).cumprod()
        max_dd, _, _ = maximum_drawdown(cum_values)
    
    # Avoid division by zero
    if max_dd == 0:
        return float('inf') if annualized_return > 0 else 0.0
    
    # Calmar ratio = annualized return / abs(maximum drawdown)
    calmar = annualized_return / abs(max_dd)
    
    return calmar 