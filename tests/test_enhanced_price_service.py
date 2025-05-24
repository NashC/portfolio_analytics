"""
Tests for enhanced price service with guaranteed coverage (AP-3).
"""
import pytest
from datetime import date, datetime, timedelta
from decimal import Decimal
from unittest.mock import Mock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base, Asset, DataSource, PriceData, PositionDaily, Account, User, Institution
from app.services.price_service import PriceService


@pytest.fixture
def test_db():
    """Create a test database with SQLite in-memory."""
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return Session(), engine


@pytest.fixture
def sample_data(test_db):
    """Create sample data for testing."""
    session, engine = test_db
    
    # Create user and institution
    user = User(username="testuser", email="test@example.com")
    institution = Institution(name="Test Exchange", type="exchange")
    session.add_all([user, institution])
    session.commit()
    
    # Create account
    account = Account(
        user_id=user.user_id,
        institution_id=institution.institution_id,
        account_name="Test Account"
    )
    session.add(account)
    session.commit()
    
    # Create assets
    btc = Asset(symbol="BTC", name="Bitcoin", type="crypto")
    eth = Asset(symbol="ETH", name="Ethereum", type="crypto")
    aapl = Asset(symbol="AAPL", name="Apple Inc", type="stock")
    usdc = Asset(symbol="USDC", name="USD Coin", type="crypto")
    session.add_all([btc, eth, aapl, usdc])
    session.commit()
    
    # Create data source
    source = DataSource(name="Test Source", type="exchange", priority=100)
    session.add(source)
    session.commit()
    
    return {
        'session': session,
        'user': user,
        'account': account,
        'btc': btc,
        'eth': eth,
        'aapl': aapl,
        'usdc': usdc,
        'source': source
    }


@pytest.fixture
def price_service():
    """Create a price service instance."""
    return PriceService()


def test_get_price_with_fallback_database_hit(sample_data, price_service):
    """Test get_price_with_fallback when price exists in database."""
    session = sample_data['session']
    btc = sample_data['btc']
    source = sample_data['source']
    
    # Add price data to database
    price_data = PriceData(
        asset_id=btc.asset_id,
        source_id=source.source_id,
        date=date(2024, 1, 1),
        open=50000.0,
        high=51000.0,
        low=49000.0,
        close=50500.0,
        confidence_score=100.0
    )
    session.add(price_data)
    session.commit()
    
    # Mock the get_db function to return our test session
    with patch('app.services.price_service.get_db') as mock_get_db:
        mock_get_db.return_value.__next__.return_value = session
        
        price = price_service.get_price_with_fallback("BTC", date(2024, 1, 1))
        assert price == 50500.0


def test_get_price_with_fallback_stablecoin(price_service):
    """Test get_price_with_fallback for stablecoins."""
    # Should return 1.0 for stablecoins without hitting database
    with patch('app.services.price_service.get_db') as mock_get_db:
        # Mock empty database response
        mock_session = Mock()
        mock_session.execute.return_value.scalar_one_or_none.return_value = None
        mock_session.__enter__ = Mock(return_value=mock_session)
        mock_session.__exit__ = Mock(return_value=None)
        
        # Create a proper context manager mock
        mock_context_manager = Mock()
        mock_context_manager.__enter__ = Mock(return_value=mock_session)
        mock_context_manager.__exit__ = Mock(return_value=None)
        
        # Mock get_db to return a new iterator each time it's called
        def mock_get_db_func():
            return iter([mock_context_manager])
        
        mock_get_db.side_effect = mock_get_db_func
        
        price = price_service.get_price_with_fallback("USDC", date(2024, 1, 1))
        assert price == 1.0
        
        price = price_service.get_price_with_fallback("USDT", date(2024, 1, 1))
        assert price == 1.0


@patch('app.services.price_service.yf.Ticker')
def test_get_price_with_fallback_stock_external(mock_ticker, sample_data, price_service):
    """Test get_price_with_fallback fetching stock price from yfinance."""
    session = sample_data['session']
    
    # Mock yfinance response
    import pandas as pd
    mock_data = pd.DataFrame({
        'Close': [150.0]
    }, index=pd.to_datetime(['2024-01-01']))
    
    mock_ticker_instance = Mock()
    mock_ticker_instance.history.return_value = mock_data
    mock_ticker.return_value = mock_ticker_instance
    
    # Mock the get_db function
    with patch('app.services.price_service.get_db') as mock_get_db:
        mock_session = Mock()
        mock_session.execute.return_value.scalar_one_or_none.return_value = None
        mock_session.__enter__ = Mock(return_value=mock_session)
        mock_session.__exit__ = Mock(return_value=None)
        
        mock_get_db.return_value = iter([mock_session])
        
        price = price_service.get_price_with_fallback("AAPL", date(2024, 1, 1))
        assert price == 150.0


@patch('app.services.price_service.requests.get')
def test_get_price_with_fallback_crypto_external(mock_get, sample_data, price_service):
    """Test get_price_with_fallback fetching crypto price from CoinGecko."""
    session = sample_data['session']
    
    # Mock CoinGecko response
    mock_response = Mock()
    mock_response.json.return_value = {
        'market_data': {
            'current_price': {
                'usd': 45000.0
            }
        }
    }
    mock_response.raise_for_status.return_value = None
    mock_get.return_value = mock_response
    
    # Mock the get_db function
    with patch('app.services.price_service.get_db') as mock_get_db:
        mock_get_db.return_value.__next__.return_value = session
        
        price = price_service.get_price_with_fallback("BTC", date(2024, 1, 1))
        assert price == 45000.0


def test_get_price_with_fallback_unsupported_asset(sample_data, price_service):
    """Test get_price_with_fallback with unsupported asset."""
    session = sample_data['session']
    
    with patch('app.services.price_service.get_db') as mock_get_db:
        mock_get_db.return_value.__next__.return_value = session
        
        with pytest.raises(ValueError) as exc_info:
            price_service.get_price_with_fallback("UNKNOWN", date(2024, 1, 1))
        
        assert "Price not available" in str(exc_info.value)


def test_ensure_price_coverage_all_covered(sample_data, price_service):
    """Test ensure_price_coverage when all prices are already in database."""
    session = sample_data['session']
    btc = sample_data['btc']
    account = sample_data['account']
    source = sample_data['source']
    
    # Create position
    position = PositionDaily(
        date=date(2024, 1, 1),
        account_id=account.account_id,
        asset_id=btc.asset_id,
        quantity=Decimal('1.0')
    )
    session.add(position)
    
    # Create corresponding price data
    price_data = PriceData(
        asset_id=btc.asset_id,
        source_id=source.source_id,
        date=date(2024, 1, 1),
        close=50000.0,
        open=50000.0,
        high=50000.0,
        low=50000.0,
        confidence_score=100.0
    )
    session.add(price_data)
    session.commit()
    
    # Mock the get_db function
    with patch('app.services.price_service.get_db') as mock_get_db:
        mock_get_db.return_value.__next__.return_value = session
        
        stats = price_service.ensure_price_coverage(
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 1)
        )
        
        assert stats['total_required'] == 1
        assert stats['found_in_db'] == 1
        assert stats['fetched_external'] == 0
        assert stats['missing'] == 0


@patch('app.services.price_service.requests.get')
def test_ensure_price_coverage_fetch_external(mock_get, sample_data, price_service):
    """Test ensure_price_coverage fetching missing prices externally."""
    session = sample_data['session']
    btc = sample_data['btc']
    account = sample_data['account']
    source = sample_data['source']
    
    # Create position without corresponding price data
    position = PositionDaily(
        date=date(2024, 1, 1),
        account_id=account.account_id,
        asset_id=btc.asset_id,
        quantity=Decimal('1.0')
    )
    session.add(position)
    session.commit()
    
    # Mock CoinGecko response
    mock_response = Mock()
    mock_response.json.return_value = {
        'market_data': {
            'current_price': {
                'usd': 45000.0
            }
        }
    }
    mock_response.raise_for_status.return_value = None
    mock_get.return_value = mock_response
    
    # Mock the get_db function to return the same session
    with patch('app.services.price_service.get_db') as mock_get_db:
        # Create a proper context manager mock that returns the same session
        mock_context_manager = Mock()
        mock_context_manager.__enter__ = Mock(return_value=session)
        mock_context_manager.__exit__ = Mock(return_value=None)
        
        # Mock get_db to return a new iterator each time it's called
        def mock_get_db_func():
            return iter([mock_context_manager])
        
        mock_get_db.side_effect = mock_get_db_func
        
        stats = price_service.ensure_price_coverage(
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 1)
        )
        
        assert stats['total_required'] == 1
        assert stats['found_in_db'] == 0
        assert stats['fetched_external'] == 1
        assert stats['missing'] == 0
        
        # Verify price was stored in database
        stored_price = session.query(PriceData).filter_by(
            asset_id=btc.asset_id,
            date=date(2024, 1, 1)
        ).first()
        assert stored_price is not None
        assert stored_price.close == 45000.0


def test_validate_position_price_coverage_complete(sample_data, price_service):
    """Test validate_position_price_coverage with complete coverage."""
    session = sample_data['session']
    btc = sample_data['btc']
    account = sample_data['account']
    source = sample_data['source']
    
    # Create position and corresponding price
    position = PositionDaily(
        date=date(2024, 1, 1),
        account_id=account.account_id,
        asset_id=btc.asset_id,
        quantity=Decimal('1.0')
    )
    price_data = PriceData(
        asset_id=btc.asset_id,
        source_id=source.source_id,
        date=date(2024, 1, 1),
        close=50000.0,
        open=50000.0,
        high=50000.0,
        low=50000.0
    )
    session.add_all([position, price_data])
    session.commit()
    
    # Mock the get_db function
    with patch('app.services.price_service.get_db') as mock_get_db:
        mock_get_db.return_value.__next__.return_value = session
        
        result = price_service.validate_position_price_coverage(
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 1)
        )
        
        assert result['total_positions'] == 1
        assert result['covered_positions'] == 1
        assert result['missing_positions'] == 0
        assert result['coverage_percentage'] == 100.0
        assert result['is_complete'] is True


def test_validate_position_price_coverage_missing(sample_data, price_service):
    """Test validate_position_price_coverage with missing prices."""
    session = sample_data['session']
    btc = sample_data['btc']
    account = sample_data['account']
    
    # Create position without corresponding price
    position = PositionDaily(
        date=date(2024, 1, 1),
        account_id=account.account_id,
        asset_id=btc.asset_id,
        quantity=Decimal('1.0')
    )
    session.add(position)
    session.commit()
    
    # Mock the get_db function
    with patch('app.services.price_service.get_db') as mock_get_db:
        mock_get_db.return_value.__next__.return_value = session
        
        result = price_service.validate_position_price_coverage(
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 1)
        )
        
        assert result['total_positions'] == 1
        assert result['covered_positions'] == 0
        assert result['missing_positions'] == 1
        assert result['coverage_percentage'] == 0.0
        assert result['is_complete'] is False
        assert len(result['missing_prices']) == 1
        assert result['missing_prices'][0]['symbol'] == 'BTC'


def test_validate_position_price_coverage_zero_positions(sample_data, price_service):
    """Test validate_position_price_coverage ignores zero positions."""
    session = sample_data['session']
    btc = sample_data['btc']
    account = sample_data['account']
    
    # Create position with zero quantity
    position = PositionDaily(
        date=date(2024, 1, 1),
        account_id=account.account_id,
        asset_id=btc.asset_id,
        quantity=Decimal('0.0')
    )
    session.add(position)
    session.commit()
    
    # Mock the get_db function
    with patch('app.services.price_service.get_db') as mock_get_db:
        mock_get_db.return_value.__next__.return_value = session
        
        result = price_service.validate_position_price_coverage(
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 1)
        )
        
        # Should ignore zero positions
        assert result['total_positions'] == 0
        assert result['is_complete'] is True 