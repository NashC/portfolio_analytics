"""
Tests for Returns Calculation Library (AP-5)
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, date

from app.analytics.returns import (
    daily_returns, cumulative_returns, twrr, rolling_returns,
    volatility, sharpe_ratio, maximum_drawdown, calmar_ratio
)


class TestDailyReturns:
    """Test daily_returns function."""
    
    def test_daily_returns_basic(self):
        """Test basic daily returns calculation."""
        prices = pd.Series([100, 102, 101, 105], 
                          index=pd.date_range('2024-01-01', periods=4))
        returns = daily_returns(prices)
        
        assert len(returns) == 3  # One less than input due to pct_change
        assert abs(returns.iloc[0] - 0.02) < 1e-10  # (102-100)/100
        assert abs(returns.iloc[1] - (-0.0098039)) < 1e-6  # (101-102)/102
        assert abs(returns.iloc[2] - 0.0396039) < 1e-6  # (105-101)/101
    
    def test_daily_returns_empty_series(self):
        """Test daily returns with empty series."""
        empty_series = pd.Series([], dtype=float)
        with pytest.raises(ValueError, match="Input series cannot be empty"):
            daily_returns(empty_series)
    
    def test_daily_returns_non_numeric(self):
        """Test daily returns with non-numeric data."""
        text_series = pd.Series(['a', 'b', 'c'])
        with pytest.raises(ValueError, match="Input series must contain numeric values"):
            daily_returns(text_series)
    
    def test_daily_returns_single_value(self):
        """Test daily returns with single value."""
        single_value = pd.Series([100], index=[pd.Timestamp('2024-01-01')])
        returns = daily_returns(single_value)
        assert len(returns) == 0  # No returns from single value


class TestCumulativeReturns:
    """Test cumulative_returns function."""
    
    def test_cumulative_returns_basic(self):
        """Test basic cumulative returns calculation."""
        daily_rets = pd.Series([0.02, -0.01, 0.04], 
                              index=pd.date_range('2024-01-01', periods=3))
        cum_rets = cumulative_returns(daily_rets)
        
        assert len(cum_rets) == 3
        assert abs(cum_rets.iloc[0] - 0.02) < 1e-10  # First return
        assert abs(cum_rets.iloc[1] - 0.0098) < 1e-6  # (1.02 * 0.99) - 1
        assert abs(cum_rets.iloc[2] - 0.050192) < 1e-6  # (1.02 * 0.99 * 1.04) - 1
    
    def test_cumulative_returns_empty_series(self):
        """Test cumulative returns with empty series."""
        empty_series = pd.Series([], dtype=float)
        with pytest.raises(ValueError, match="Input series cannot be empty"):
            cumulative_returns(empty_series)
    
    def test_cumulative_returns_zero_returns(self):
        """Test cumulative returns with zero returns."""
        zero_rets = pd.Series([0.0, 0.0, 0.0], 
                             index=pd.date_range('2024-01-01', periods=3))
        cum_rets = cumulative_returns(zero_rets)
        
        assert all(abs(ret) < 1e-10 for ret in cum_rets)  # All should be ~0


class TestTWRR:
    """Test twrr function."""
    
    def test_twrr_no_cash_flows(self):
        """Test TWRR without cash flows."""
        values = pd.Series([1000, 1100, 1050, 1200], 
                          index=pd.date_range('2024-01-01', periods=4))
        twrr_result = twrr(values)
        
        assert isinstance(twrr_result, float)
        assert twrr_result > 0  # Should be positive for this growth scenario
    
    def test_twrr_with_cash_flows(self):
        """Test TWRR with cash flows."""
        values = pd.Series([1000, 1100, 1200, 1300], 
                          index=pd.date_range('2024-01-01', periods=4))
        cash_flows = pd.Series([0, 0, 100, 0], 
                              index=pd.date_range('2024-01-01', periods=4))
        
        twrr_result = twrr(values, cash_flows)
        assert isinstance(twrr_result, float)
    
    def test_twrr_empty_series(self):
        """Test TWRR with empty series."""
        empty_series = pd.Series([], dtype=float)
        with pytest.raises(ValueError, match="Input series cannot be empty"):
            twrr(empty_series)
    
    def test_twrr_insufficient_data(self):
        """Test TWRR with insufficient data points."""
        single_value = pd.Series([1000], index=[pd.Timestamp('2024-01-01')])
        with pytest.raises(ValueError, match="Need at least 2 data points"):
            twrr(single_value)


class TestRollingReturns:
    """Test rolling_returns function."""
    
    def test_rolling_returns_basic(self):
        """Test basic rolling returns calculation."""
        values = pd.Series([100, 102, 101, 105, 108], 
                          index=pd.date_range('2024-01-01', periods=5))
        rolling_rets = rolling_returns(values, window=3)
        
        assert len(rolling_rets) == 3  # 5 - 3 + 1
        # First rolling return: (101-100)/100 = 0.01
        assert abs(rolling_rets.iloc[0] - 0.01) < 1e-10
    
    def test_rolling_returns_invalid_window(self):
        """Test rolling returns with invalid window."""
        values = pd.Series([100, 102, 101], 
                          index=pd.date_range('2024-01-01', periods=3))
        
        with pytest.raises(ValueError, match="Window must be between 1 and 3"):
            rolling_returns(values, window=0)
        
        with pytest.raises(ValueError, match="Window must be between 1 and 3"):
            rolling_returns(values, window=5)


class TestVolatility:
    """Test volatility function."""
    
    def test_volatility_basic(self):
        """Test basic volatility calculation."""
        returns = pd.Series([0.01, -0.02, 0.015, -0.005])
        vol = volatility(returns, annualized=True)
        
        assert isinstance(vol, float)
        assert vol > 0
    
    def test_volatility_not_annualized(self):
        """Test volatility without annualization."""
        returns = pd.Series([0.01, -0.02, 0.015, -0.005])
        vol_daily = volatility(returns, annualized=False)
        vol_annual = volatility(returns, annualized=True)
        
        # Annualized should be larger
        assert vol_annual > vol_daily
        assert abs(vol_annual - vol_daily * np.sqrt(252)) < 1e-10
    
    def test_volatility_zero_variance(self):
        """Test volatility with zero variance."""
        constant_returns = pd.Series([0.01, 0.01, 0.01, 0.01])
        vol = volatility(constant_returns)
        
        assert vol == 0.0


class TestSharpeRatio:
    """Test sharpe_ratio function."""
    
    def test_sharpe_ratio_basic(self):
        """Test basic Sharpe ratio calculation."""
        returns = pd.Series([0.01, -0.02, 0.015, -0.005])
        sr = sharpe_ratio(returns, risk_free_rate=0.02)
        
        assert isinstance(sr, float)
    
    def test_sharpe_ratio_zero_volatility(self):
        """Test Sharpe ratio with zero volatility."""
        constant_returns = pd.Series([0.01, 0.01, 0.01, 0.01])
        sr = sharpe_ratio(constant_returns)
        
        assert sr == 0.0
    
    def test_sharpe_ratio_custom_risk_free_rate(self):
        """Test Sharpe ratio with custom risk-free rate."""
        returns = pd.Series([0.01, -0.02, 0.015, -0.005])
        sr1 = sharpe_ratio(returns, risk_free_rate=0.02)
        sr2 = sharpe_ratio(returns, risk_free_rate=0.05)
        
        # Higher risk-free rate should result in lower Sharpe ratio
        assert sr1 > sr2


class TestMaximumDrawdown:
    """Test maximum_drawdown function."""
    
    def test_maximum_drawdown_basic(self):
        """Test basic maximum drawdown calculation."""
        values = pd.Series([100, 110, 90, 95], 
                          index=pd.date_range('2024-01-01', periods=4))
        max_dd, peak_date, trough_date = maximum_drawdown(values)
        
        assert isinstance(max_dd, float)
        assert max_dd < 0  # Drawdown should be negative
        assert abs(max_dd - (-0.18181818181818182)) < 1e-10  # (90-110)/110
        assert isinstance(peak_date, pd.Timestamp)
        assert isinstance(trough_date, pd.Timestamp)
    
    def test_maximum_drawdown_no_drawdown(self):
        """Test maximum drawdown with no drawdown (monotonic increase)."""
        values = pd.Series([100, 110, 120, 130], 
                          index=pd.date_range('2024-01-01', periods=4))
        max_dd, peak_date, trough_date = maximum_drawdown(values)
        
        assert max_dd == 0.0  # No drawdown
    
    def test_maximum_drawdown_empty_series(self):
        """Test maximum drawdown with empty series."""
        empty_series = pd.Series([], dtype=float)
        with pytest.raises(ValueError, match="Input series cannot be empty"):
            maximum_drawdown(empty_series)


class TestCalmarRatio:
    """Test calmar_ratio function."""
    
    def test_calmar_ratio_basic(self):
        """Test basic Calmar ratio calculation."""
        returns = pd.Series([0.01, -0.02, 0.015, -0.005])
        calmar = calmar_ratio(returns)
        
        assert isinstance(calmar, float)
    
    def test_calmar_ratio_with_provided_drawdown(self):
        """Test Calmar ratio with pre-calculated drawdown."""
        returns = pd.Series([0.01, -0.02, 0.015, -0.005])
        calmar = calmar_ratio(returns, max_dd=-0.1)
        
        assert isinstance(calmar, float)
    
    def test_calmar_ratio_zero_drawdown(self):
        """Test Calmar ratio with zero drawdown."""
        positive_returns = pd.Series([0.01, 0.02, 0.015, 0.005])
        calmar = calmar_ratio(positive_returns, max_dd=0.0)
        
        # Should return infinity for positive returns with zero drawdown
        assert calmar == float('inf')
    
    def test_calmar_ratio_empty_series(self):
        """Test Calmar ratio with empty series."""
        empty_series = pd.Series([], dtype=float)
        with pytest.raises(ValueError, match="Returns series cannot be empty"):
            calmar_ratio(empty_series)


class TestIntegration:
    """Integration tests for the returns library."""
    
    def test_complete_workflow(self):
        """Test a complete returns analysis workflow."""
        # Create sample price data
        prices = pd.Series([1000, 1020, 1010, 1050, 1080, 1060, 1100], 
                          index=pd.date_range('2024-01-01', periods=7))
        
        # Calculate daily returns
        daily_rets = daily_returns(prices)
        assert len(daily_rets) == 6
        
        # Calculate cumulative returns
        cum_rets = cumulative_returns(daily_rets)
        assert len(cum_rets) == 6
        
        # Calculate TWRR
        twrr_result = twrr(prices)
        assert isinstance(twrr_result, float)
        
        # Calculate risk metrics
        vol = volatility(daily_rets)
        sr = sharpe_ratio(daily_rets)
        max_dd, _, _ = maximum_drawdown(prices)
        calmar = calmar_ratio(daily_rets)
        
        # All should be valid numbers
        assert all(isinstance(x, float) for x in [vol, sr, max_dd, calmar])
        assert vol > 0
        assert max_dd <= 0
    
    def test_synthetic_data_accuracy(self):
        """Test with synthetic data where we know the expected results."""
        # Create data with known 10% return over 10 days
        initial_value = 1000
        final_value = 1100
        days = 10
        
        # Create geometric progression
        daily_growth = (final_value / initial_value) ** (1 / days)
        values = [initial_value * (daily_growth ** i) for i in range(days + 1)]
        prices = pd.Series(values, index=pd.date_range('2024-01-01', periods=days + 1))
        
        # Calculate returns
        daily_rets = daily_returns(prices)
        
        # All daily returns should be approximately equal
        expected_daily_return = daily_growth - 1
        for ret in daily_rets:
            assert abs(ret - expected_daily_return) < 1e-10
        
        # Cumulative return should be approximately 10%
        total_return = (1 + daily_rets).prod() - 1
        assert abs(total_return - 0.1) < 1e-10 