import pytest
import pandas as pd
from datetime import date
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import os
import tempfile

from scripts.migration import DatabaseMigration
from app.db.base import Base, Asset, DataSource, PriceData, AssetSourceMapping

@pytest.fixture
def migration():
    """Create a DatabaseMigration instance with a fresh in-memory test database."""
    return DatabaseMigration(db_path=":memory:")

@pytest.fixture
def temp_data_dir():
    """Create a temporary directory with sample data files."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Binance format
        binance_data = pd.DataFrame({
            'Date': ['2024-01-01', '2024-01-02'],
            'Symbol': ['BTCUSDT', 'ETHUSDT'],
            'Open': [40000.0, 2000.0],
            'High': [41000.0, 2100.0],
            'Low': [39000.0, 1900.0],
            'Close': [40500.0, 2050.0],
            'Volume': [1000.0, 500.0]
        })
        binance_data.to_csv(os.path.join(temp_dir, 'prices_binance_2024.csv'), index=False)
        # Coinlore format
        coinlore_data = pd.DataFrame({
            'Date': ['01/01/2024', '01/02/2024'],
            'Symbol': ['BTC', 'ETH'],
            'High': ['$41000', '$2100'],
            'Low': ['$39000', '$1900'],
            'Close': ['$40500', '$2050'],
            'Volume(CELO)': ['1000', '500']
        })
        coinlore_data.to_csv(os.path.join(temp_dir, 'prices_coinlore_2024.csv'), index=False)
        yield temp_dir

def test_setup_database(migration):
    migration.setup_database()
    with migration.engine.connect() as conn:
        result = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
        tables = [row[0] for row in result]
        assert 'assets' in tables
        assert 'data_sources' in tables
        assert 'price_data' in tables
        assert 'asset_source_mappings' in tables

def test_initialize_data_sources(migration):
    migration.setup_database()
    migration.initialize_data_sources()
    with migration.engine.connect() as conn:
        result = conn.execute(text("SELECT name, type FROM data_sources"))
        sources = [(row[0], row[1]) for row in result]
        assert ('Gemini', 'exchange') in sources
        assert ('Binance', 'exchange') in sources
        assert ('CoinMarketCap', 'aggregator') in sources

def test_get_or_create_asset(migration):
    migration.setup_database()
    asset_id = migration.get_or_create_asset('BTC')
    assert asset_id > 0
    same_asset_id = migration.get_or_create_asset('BTC')
    assert same_asset_id == asset_id
    celo_id = migration.get_or_create_asset('CGLD')
    assert celo_id > 0
    with migration.engine.connect() as conn:
        result = conn.execute(text("SELECT symbol FROM assets WHERE asset_id = :id"), {"id": celo_id})
        symbol = result.scalar()
        assert symbol == 'CELO'

def test_create_asset_source_mapping(migration):
    migration.setup_database()
    migration.initialize_data_sources()
    asset_id = migration.get_or_create_asset('BTC')
    with migration.engine.connect() as conn:
        result = conn.execute(text("SELECT source_id FROM data_sources WHERE name = :name"), {"name": 'Binance'})
        source_id = result.scalar()
    migration.create_asset_source_mapping(asset_id, source_id, 'BTCUSDT')
    with migration.engine.connect() as conn:
        result = conn.execute(text("""
            SELECT source_symbol, is_active 
            FROM asset_source_mappings 
            WHERE asset_id = :asset_id AND source_id = :source_id
        """), {"asset_id": asset_id, "source_id": source_id})
        mapping = result.fetchone()
        assert mapping is not None
        assert mapping[0] == 'BTCUSDT'
        assert mapping[1] == 1

def test_import_csv_data(migration, temp_data_dir):
    migration.setup_database()
    migration.initialize_data_sources()
    binance_file = os.path.join(temp_data_dir, 'prices_binance_2024.csv')
    migration.import_csv_data(binance_file)
    with migration.engine.connect() as conn:
        result = conn.execute(text("""
            SELECT COUNT(*) 
            FROM price_data p
            JOIN assets a ON p.asset_id = a.asset_id
            WHERE a.symbol = :symbol
        """), {"symbol": 'BTC'})
        count = result.scalar()
        assert count > 0

def test_migrate_all_data(migration, temp_data_dir):
    migration.migrate_all_data(temp_data_dir)
    with migration.engine.connect() as conn:
        result = conn.execute(text("SELECT COUNT(*) FROM assets"))
        asset_count = result.scalar()
        assert asset_count > 0
        result = conn.execute(text("SELECT COUNT(*) FROM price_data"))
        price_count = result.scalar()
        assert price_count > 0
        result = conn.execute(text("SELECT COUNT(*) FROM data_sources"))
        source_count = result.scalar()
        assert source_count > 0

def test_error_handling(migration):
    migration.setup_database()
    # Should not raise, just print error
    migration.import_csv_data('nonexistent_file.csv')
    # Should still pass if no exception is raised
    assert True 