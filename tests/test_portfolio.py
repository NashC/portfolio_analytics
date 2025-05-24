import pytest
import pandas as pd
import numpy as np
from datetime import date, timedelta
from unittest.mock import Mock, patch

from app.analytics.portfolio import (
    calculate_portfolio_value,
    calculate_returns,
    calculate_volatility,
    calculate_sharpe_ratio,
    calculate_drawdown,
    calculate_correlation_matrix
)

@pytest.fixture
def mock_price_service():
    """Create a mock price service for testing."""
    mock_service = Mock()
    
    # Mock price data for BTC, ETH, USDC
    def mock_get_price_range(asset, start_date, end_date):
        if asset.upper() == 'BTC':
            date_range = pd.date_range(start=start_date, end=end_date, freq='D')
            prices = [40000.0 + i * 100 for i in range(len(date_range))]
            return pd.Series(prices, index=date_range, name='BTC')
        elif asset.upper() == 'ETH':
            date_range = pd.date_range(start=start_date, end=end_date, freq='D')
            prices = [2000.0 + i * 10 for i in range(len(date_range))]
            return pd.Series(prices, index=date_range, name='ETH')
        elif asset.upper() in ['USDC', 'USDT', 'DAI', 'BUSD', 'GUSD']:
            date_range = pd.date_range(start=start_date, end=end_date, freq='D')
            return pd.Series(1.0, index=date_range, name=asset)
        else:
            return pd.Series(dtype=float)
    
    mock_service.get_price_range.side_effect = mock_get_price_range
    return mock_service

@pytest.fixture
def sample_portfolio_data():
    """Create sample portfolio holdings data."""
    start_date = date(2024, 1, 1)
    holdings = pd.DataFrame({
        'date': [start_date + timedelta(days=i) for i in range(30)],
        'BTC': [1.0] * 30,  # 1 BTC
        'ETH': [10.0] * 30,  # 10 ETH
        'USDC': [1000.0] * 30  # 1000 USDC
    })
    holdings.set_index('date', inplace=True)
    return holdings

def test_calculate_portfolio_value(sample_portfolio_data, mock_price_service):
    """Test portfolio value calculation."""
    start_date = date(2024, 1, 1)
    end_date = date(2024, 1, 30)
    
    portfolio_value = calculate_portfolio_value(
        sample_portfolio_data,
        mock_price_service,
        start_date,
        end_date
    )
    
    assert not portfolio_value.empty
    assert len(portfolio_value) == 30
    assert all(value > 0 for value in portfolio_value['total_value'])
    assert 'BTC_value' in portfolio_value.columns
    assert 'ETH_value' in portfolio_value.columns
    assert 'USDC_value' in portfolio_value.columns

def test_calculate_returns(sample_portfolio_data, mock_price_service):
    """Test returns calculation."""
    start_date = date(2024, 1, 1)
    end_date = date(2024, 1, 30)
    
    returns = calculate_returns(
        sample_portfolio_data,
        mock_price_service,
        start_date,
        end_date
    )
    
    assert not returns.empty
    assert len(returns) == 29  # One less than portfolio value due to daily returns
    assert all(not np.isnan(value) for value in returns['total_return'])
    assert 'BTC_return' in returns.columns
    assert 'ETH_return' in returns.columns
    assert 'USDC_return' in returns.columns

def test_calculate_volatility(sample_portfolio_data, mock_price_service):
    """Test volatility calculation."""
    start_date = date(2024, 1, 1)
    end_date = date(2024, 1, 30)
    
    volatility = calculate_volatility(
        sample_portfolio_data,
        mock_price_service,
        start_date,
        end_date
    )
    
    assert isinstance(volatility, float)
    assert volatility > 0
    assert not np.isnan(volatility)

def test_calculate_sharpe_ratio(sample_portfolio_data, mock_price_service):
    """Test Sharpe ratio calculation."""
    start_date = date(2024, 1, 1)
    end_date = date(2024, 1, 30)
    
    sharpe = calculate_sharpe_ratio(
        sample_portfolio_data,
        mock_price_service,
        start_date,
        end_date
    )
    
    assert isinstance(sharpe, float)
    assert not np.isnan(sharpe)

def test_calculate_drawdown(sample_portfolio_data, mock_price_service):
    """Test drawdown calculation."""
    start_date = date(2024, 1, 1)
    end_date = date(2024, 1, 30)
    
    drawdown = calculate_drawdown(
        sample_portfolio_data,
        mock_price_service,
        start_date,
        end_date
    )
    
    assert not drawdown.empty
    assert len(drawdown) == 30
    assert all(value <= 0 for value in drawdown['drawdown'])
    assert 'peak_value' in drawdown.columns
    assert 'current_value' in drawdown.columns

def test_calculate_correlation_matrix(sample_portfolio_data, mock_price_service):
    """Test correlation matrix calculation."""
    start_date = date(2024, 1, 1)
    end_date = date(2024, 1, 30)
    
    corr_matrix = calculate_correlation_matrix(
        sample_portfolio_data,
        mock_price_service,
        start_date,
        end_date
    )
    
    assert not corr_matrix.empty
    assert 'BTC' in corr_matrix.index
    assert 'ETH' in corr_matrix.index
    assert 'USDC' in corr_matrix.index
    assert all(-1 <= value <= 1 for value in corr_matrix.values.flatten())
    assert all(np.isclose(corr_matrix.loc[asset, asset], 1.0) for asset in corr_matrix.index)

def test_error_handling(sample_portfolio_data, mock_price_service):
    """Test error handling in portfolio calculations."""
    # Test with invalid date range
    start_date = date(2024, 2, 1)  # Future date
    end_date = date(2024, 1, 30)   # Past date
    
    # Should handle gracefully without crashing
    portfolio_value = calculate_portfolio_value(
        sample_portfolio_data,
        mock_price_service,
        start_date,
        end_date
    )
    
    # Should return empty or handle gracefully
    assert isinstance(portfolio_value, pd.DataFrame) 