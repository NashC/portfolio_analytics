"""
Tests for Portfolio Analytics REST API endpoints (AP-6)
"""

import pytest
from fastapi.testclient import TestClient
from datetime import date, datetime
from unittest.mock import Mock, patch
import pandas as pd

from app.api import app


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    return TestClient(app)


@pytest.fixture
def mock_db_session():
    """Mock database session."""
    return Mock()


@pytest.fixture
def sample_portfolio_value():
    """Sample portfolio value for testing."""
    return 50000.0


@pytest.fixture
def sample_value_series():
    """Sample value series for testing."""
    dates = pd.date_range(start='2024-01-01', end='2024-01-05', freq='D', tz='UTC')
    values = [45000.0, 46000.0, 47000.0, 48000.0, 49000.0]
    return pd.Series(values, index=dates, name='portfolio_value')


class TestPortfolioValueEndpoint:
    """Test the /portfolio/value endpoint."""
    
    @patch('app.api.get_portfolio_value')
    @patch('app.api.get_db')
    def test_get_portfolio_value_success(self, mock_get_db, mock_get_portfolio_value, 
                                       client, mock_db_session, sample_portfolio_value):
        """Test successful portfolio value retrieval."""
        mock_get_db.return_value = mock_db_session
        mock_get_portfolio_value.return_value = sample_portfolio_value
        
        response = client.get("/portfolio/value?target_date=2024-01-01")
        
        assert response.status_code == 200
        data = response.json()
        assert data["date"] == "2024-01-01"
        assert data["portfolio_value"] == sample_portfolio_value
        assert data["currency"] == "USD"
        assert data["account_ids"] is None
        
        mock_get_portfolio_value.assert_called_once_with(date(2024, 1, 1), None)
    
    @patch('app.api.get_portfolio_value')
    @patch('app.api.get_db')
    def test_get_portfolio_value_with_account_ids(self, mock_get_db, mock_get_portfolio_value,
                                                 client, mock_db_session, sample_portfolio_value):
        """Test portfolio value retrieval with account IDs filter."""
        mock_get_db.return_value = mock_db_session
        mock_get_portfolio_value.return_value = sample_portfolio_value
        
        response = client.get("/portfolio/value?target_date=2024-01-01&account_ids=1&account_ids=2")
        
        assert response.status_code == 200
        data = response.json()
        assert data["account_ids"] == [1, 2]
        
        mock_get_portfolio_value.assert_called_once_with(date(2024, 1, 1), [1, 2])
    
    @patch('app.api.get_portfolio_value')
    @patch('app.api.get_db')
    def test_get_portfolio_value_default_date(self, mock_get_db, mock_get_portfolio_value,
                                            client, mock_db_session, sample_portfolio_value):
        """Test portfolio value retrieval with default date (today)."""
        mock_get_db.return_value = mock_db_session
        mock_get_portfolio_value.return_value = sample_portfolio_value
        
        response = client.get("/portfolio/value")
        
        assert response.status_code == 200
        data = response.json()
        assert data["date"] == date.today().isoformat()
        
        mock_get_portfolio_value.assert_called_once_with(date.today(), None)
    
    def test_get_portfolio_value_invalid_date(self, client):
        """Test portfolio value retrieval with invalid date format."""
        response = client.get("/portfolio/value?target_date=invalid-date")
        
        assert response.status_code == 400
        assert "Invalid date format" in response.json()["detail"]
    
    @patch('app.api.get_portfolio_value')
    @patch('app.api.get_db')
    def test_get_portfolio_value_error(self, mock_get_db, mock_get_portfolio_value,
                                     client, mock_db_session):
        """Test portfolio value retrieval with error."""
        mock_get_db.return_value = mock_db_session
        mock_get_portfolio_value.side_effect = Exception("Database error")
        
        response = client.get("/portfolio/value?target_date=2024-01-01")
        
        assert response.status_code == 500
        assert "Error calculating portfolio value" in response.json()["detail"]


class TestPortfolioValueSeriesEndpoint:
    """Test the /portfolio/value/series endpoint."""
    
    @patch('app.api.get_value_series')
    @patch('app.api.get_db')
    def test_get_value_series_success(self, mock_get_db, mock_get_value_series,
                                    client, mock_db_session, sample_value_series):
        """Test successful value series retrieval."""
        mock_get_db.return_value = mock_db_session
        mock_get_value_series.return_value = sample_value_series
        
        response = client.get("/portfolio/value/series?start_date=2024-01-01&end_date=2024-01-05")
        
        assert response.status_code == 200
        data = response.json()
        assert data["start_date"] == "2024-01-01"
        assert data["end_date"] == "2024-01-05"
        assert data["currency"] == "USD"
        assert len(data["data"]) == 5
        assert "2024-01-01" in data["data"]
        assert data["data"]["2024-01-01"] == 45000.0
        
        mock_get_value_series.assert_called_once_with(date(2024, 1, 1), date(2024, 1, 5), None)
    
    @patch('app.api.get_value_series')
    @patch('app.api.get_db')
    def test_get_value_series_with_account_ids(self, mock_get_db, mock_get_value_series,
                                             client, mock_db_session, sample_value_series):
        """Test value series retrieval with account IDs filter."""
        mock_get_db.return_value = mock_db_session
        mock_get_value_series.return_value = sample_value_series
        
        response = client.get("/portfolio/value/series?start_date=2024-01-01&end_date=2024-01-05&account_ids=1")
        
        assert response.status_code == 200
        data = response.json()
        assert data["account_ids"] == [1]
        
        mock_get_value_series.assert_called_once_with(date(2024, 1, 1), date(2024, 1, 5), [1])
    
    def test_get_value_series_missing_dates(self, client):
        """Test value series retrieval with missing dates."""
        response = client.get("/portfolio/value/series")
        
        assert response.status_code == 422  # FastAPI validation error
    
    def test_get_value_series_invalid_dates(self, client):
        """Test value series retrieval with invalid date format."""
        response = client.get("/portfolio/value/series?start_date=invalid&end_date=2024-01-05")
        
        assert response.status_code == 400
        assert "Invalid date format" in response.json()["detail"]
    
    def test_get_value_series_invalid_date_range(self, client):
        """Test value series retrieval with invalid date range."""
        response = client.get("/portfolio/value/series?start_date=2024-01-05&end_date=2024-01-01")
        
        assert response.status_code == 400
        assert "Start date must be before end date" in response.json()["detail"]


class TestPortfolioReturnsEndpoint:
    """Test the /portfolio/returns endpoint."""
    
    @patch('app.api.get_value_series')
    @patch('app.api.get_db')
    def test_get_portfolio_returns_success(self, mock_get_db, mock_get_value_series,
                                         client, mock_db_session, sample_value_series):
        """Test successful portfolio returns retrieval."""
        mock_get_db.return_value = mock_db_session
        mock_get_value_series.return_value = sample_value_series
        
        response = client.get("/portfolio/returns?start_date=2024-01-01&end_date=2024-01-05")
        
        assert response.status_code == 200
        data = response.json()
        assert data["start_date"] == "2024-01-01"
        assert data["end_date"] == "2024-01-05"
        assert "daily_returns" in data
        assert "cumulative_returns" in data
        
        # Check that we have 4 daily returns (5 values - 1 for pct_change)
        assert len(data["daily_returns"]) == 4
        assert len(data["cumulative_returns"]) == 4
        
        mock_get_value_series.assert_called_once_with(date(2024, 1, 1), date(2024, 1, 5), None)
    
    def test_get_portfolio_returns_invalid_dates(self, client):
        """Test portfolio returns retrieval with invalid date format."""
        response = client.get("/portfolio/returns?start_date=invalid&end_date=2024-01-05")
        
        assert response.status_code == 400
        assert "Invalid date format" in response.json()["detail"]


class TestHealthEndpoint:
    """Test the /health endpoint."""
    
    def test_health_check(self, client):
        """Test health check endpoint."""
        response = client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "portfolio-analytics-api"


class TestAPIIntegration:
    """Integration tests for the API."""
    
    @patch('app.api.get_portfolio_value')
    @patch('app.api.get_value_series')
    @patch('app.api.get_db')
    def test_api_workflow(self, mock_get_db, mock_get_value_series, mock_get_portfolio_value,
                         client, mock_db_session, sample_value_series, sample_portfolio_value):
        """Test a complete API workflow."""
        mock_get_db.return_value = mock_db_session
        mock_get_portfolio_value.return_value = sample_portfolio_value
        mock_get_value_series.return_value = sample_value_series
        
        # Test health check
        health_response = client.get("/health")
        assert health_response.status_code == 200
        
        # Test single value
        value_response = client.get("/portfolio/value?target_date=2024-01-01")
        assert value_response.status_code == 200
        
        # Test value series
        series_response = client.get("/portfolio/value/series?start_date=2024-01-01&end_date=2024-01-05")
        assert series_response.status_code == 200
        
        # Test returns
        returns_response = client.get("/portfolio/returns?start_date=2024-01-01&end_date=2024-01-05")
        assert returns_response.status_code == 200 