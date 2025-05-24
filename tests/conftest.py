import sys
import os
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import date, timedelta
import pandas as pd

# Add the project root to the Python path.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.db.base import Base, Asset, DataSource, PriceData
from app.services.price_service import PriceService

@pytest.fixture(scope="session")
def test_db():
    """Create a test database with SQLite in-memory."""
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return Session()

@pytest.fixture(scope="session")
def price_service(test_db):
    """Create a PriceService instance with test database."""
    return PriceService()

@pytest.fixture(scope="session")
def sample_assets(test_db):
    """Create sample assets in the test database."""
    assets = [
        Asset(symbol='BTC'),
        Asset(symbol='ETH'),
        Asset(symbol='USDC'),
        Asset(symbol='CELO'),
    ]
    test_db.add_all(assets)
    test_db.commit()
    return assets

@pytest.fixture(scope="session")
def sample_data_source(test_db):
    """Create a sample data source in the test database."""
    source = DataSource(name='test_source', priority=1)
    test_db.add(source)
    test_db.commit()
    return source

@pytest.fixture(scope="session")
def sample_price_data(test_db, sample_assets, sample_data_source):
    """Create sample price data in the test database."""
    start_date = date(2024, 1, 1)
    prices = []
    
    for i in range(30):
        current_date = start_date + timedelta(days=i)
        for asset in sample_assets:
            if asset.symbol == 'USDC':
                # USDC is a stablecoin
                price = 1.0
            else:
                # Simulate price movement
                base_price = 40000.0 if asset.symbol == 'BTC' else 2000.0
                price = base_price + i * (100 if asset.symbol == 'BTC' else 10)
            
            price_data = PriceData(
                asset_id=asset.id,
                source_id=sample_data_source.id,
                date=current_date,
                open=price,
                high=price * 1.02,
                low=price * 0.98,
                close=price,
                volume=1000.0,
                confidence_score=1.0
            )
            prices.append(price_data)
    
    test_db.add_all(prices)
    test_db.commit()
    return prices

@pytest.fixture(scope="session")
def sample_portfolio_data(sample_assets):
    """Create sample portfolio holdings data."""
    start_date = date(2024, 1, 1)
    holdings = pd.DataFrame({
        'date': [start_date + timedelta(days=i) for i in range(30)],
        'BTC': [1.0] * 30,  # 1 BTC
        'ETH': [10.0] * 30,  # 10 ETH
        'USDC': [1000.0] * 30,  # 1000 USDC
        'CELO': [100.0] * 30  # 100 CELO
    })
    holdings.set_index('date', inplace=True)
    return holdings
