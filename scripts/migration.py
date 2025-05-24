import os
import pandas as pd
from datetime import datetime, date
import json
from typing import Dict, List, Optional
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session
from app.db.base import Asset, DataSource, PriceData, AssetSourceMapping
from app.db.session import get_db

def date_handler(obj):
    """JSON serializer for datetime objects"""
    if isinstance(obj, (datetime, pd.Timestamp)):
        return obj.isoformat()
    raise TypeError(f"Type {type(obj)} not serializable")

class DatabaseMigration:
    def __init__(self, db_path: str = "data/databases/portfolio.db"):
        self.db_path = os.path.abspath(db_path)
        self.engine = create_engine(f"sqlite:///{self.db_path}")
        
        # Initialize data sources
        self.data_sources = {
            'gemini': {'name': 'Gemini', 'type': 'exchange'},
            'bitfinex': {'name': 'Bitfinex', 'type': 'exchange'},
            'bitstamp': {'name': 'Bitstamp', 'type': 'exchange'},
            'coinlore': {'name': 'Coinlore', 'type': 'aggregator'},
            'coinmarketcap': {'name': 'CoinMarketCap', 'type': 'aggregator'},
            'binance': {'name': 'Binance', 'type': 'exchange'}
        }
        
        # Initialize source IDs
        self.source_ids = {}
        
        # Asset symbol mappings (for rebranding)
        self.asset_mappings = {
            'CGLD': 'CELO',  # Celo rebranded from CGLD
            'ETH2': 'ETH'    # ETH2 uses ETH price
        }
        
    def setup_database(self):
        """Create database tables using schema.sql"""
        try:
            # Updated schema path for reorganized structure
            schema_path = os.path.join("data", "databases", "schema.sql")
            print(f"Loading schema from: {schema_path}")
            with open(schema_path, 'r') as f:
                schema = f.read()
            # Use raw SQLite connection for executescript
            with self.engine.begin() as connection:
                raw_conn = connection.connection
                raw_conn.executescript(schema)
            print("Database schema created successfully")
        except Exception as e:
            print(f"Error creating database schema: {e}")
            raise
        
    def initialize_data_sources(self):
        """Insert data sources and get their IDs (idempotent)."""
        try:
            with Session(self.engine) as session:
                for source_key, source_data in self.data_sources.items():
                    # Check if data source already exists
                    existing = session.execute(
                        select(DataSource).where(DataSource.name == source_data['name'])
                    ).scalar_one_or_none()
                    if existing:
                        self.source_ids[source_key] = existing.source_id
                        continue
                    # Create new data source
                    data_source = DataSource(
                        name=source_data['name'],
                        type=source_data['type']
                    )
                    session.add(data_source)
                    session.commit()
                    # Get source ID
                    result = session.execute(
                        select(DataSource).where(DataSource.name == source_data['name'])
                    ).scalar_one_or_none()
                    if result:
                        self.source_ids[source_key] = result.source_id
                    else:
                        print(f"Warning: Could not find source_id for {source_data['name']}")
            print(f"Data sources initialized: {list(self.source_ids.keys())}")
        except Exception as e:
            print(f"Error initializing data sources: {e}")
            raise
        
    def get_or_create_asset(self, symbol: str, asset_type: str = 'crypto') -> int:
        """Get asset_id or create new asset if it doesn't exist"""
        try:
            # Remove USD suffix and convert to uppercase
            base_symbol = symbol.upper()
            if base_symbol.endswith('USD'):
                base_symbol = base_symbol[:-3]
            
            # Remove any trailing slash if present
            if base_symbol.endswith('/'):
                base_symbol = base_symbol[:-1]
            
            # Apply asset mapping if exists
            base_symbol = self.asset_mappings.get(base_symbol, base_symbol)
            
            with Session(self.engine) as session:
                # Check if asset exists
                result = session.execute(
                    select(Asset).where(Asset.symbol == base_symbol)
                ).scalar_one_or_none()
                
                if result:
                    return result.asset_id
                
                # Create new asset
                print(f"Creating new asset: {base_symbol}")
                new_asset = Asset(
                    symbol=base_symbol,
                    name=base_symbol  # Add name field
                )
                session.add(new_asset)
                session.commit()
                
                # Get the new asset ID
                result = session.execute(
                    select(Asset).where(Asset.symbol == base_symbol)
                ).scalar_one_or_none()
                
                if not result:
                    raise ValueError(f"Failed to create asset {base_symbol}")
                    
                return result.asset_id
        except Exception as e:
            print(f"Error creating asset {symbol}: {e}")
            raise
        
    def create_asset_source_mapping(self, asset_id: int, source_id: int, source_symbol: str):
        """Create mapping between asset and data source"""
        try:
            with Session(self.engine) as session:
                # Check if mapping already exists
                existing = session.execute(
                    select(AssetSourceMapping).where(
                        AssetSourceMapping.asset_id == asset_id,
                        AssetSourceMapping.source_id == source_id
                    )
                ).scalar_one_or_none()
                
                if existing:
                    # Update existing mapping
                    existing.source_symbol = source_symbol
                    existing.is_active = True
                    existing.last_successful_fetch = datetime.now()
                else:
                    # Create new mapping
                    mapping = AssetSourceMapping(
                        asset_id=asset_id,
                        source_id=source_id,
                        source_symbol=source_symbol,
                        is_active=True,
                        last_successful_fetch=datetime.now()
                    )
                    session.add(mapping)
                
                session.commit()
        except Exception as e:
            print(f"Error creating asset source mapping: {e}")
            raise
        
    def import_csv_data(self, file_path):
        if not os.path.exists(file_path):
            print(f"File not found: {file_path}")
            return

        # Extract source key from filename
        filename = os.path.basename(file_path)
        source_key = filename.split('_')[-2]  # Get the second to last part after splitting by '_'

        try:
            # Get source ID
            source_id = self.source_ids.get(source_key)
            if not source_id:
                print(f"Unknown source: {source_key}")
                return

            # Read CSV file
            df = pd.read_csv(file_path)
            
            with Session(self.engine) as session:
                # Process each row
                for _, row in df.iterrows():
                    try:
                        # Extract date based on source
                        if source_key == 'binance':
                            date_str = row['Date']
                        elif source_key == 'coinlore':
                            # Convert MM/DD/YYYY to YYYY-MM-DD
                            date_str = datetime.strptime(row['Date'], '%m/%d/%Y').strftime('%Y-%m-%d')
                        else:
                            date_str = row['date']
                        
                        # Convert pandas Timestamp to string if needed
                        if isinstance(date_str, pd.Timestamp):
                            date_str = date_str.strftime('%Y-%m-%d')
                        
                        # Convert string date to Python date object
                        if isinstance(date_str, str):
                            # Handle different date formats
                            try:
                                if ' ' in date_str:  # Has time component
                                    date_obj = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S').date()
                                else:  # Date only
                                    date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
                            except ValueError:
                                # Try alternative formats
                                try:
                                    date_obj = datetime.strptime(date_str, '%m/%d/%Y').date()
                                except ValueError:
                                    print(f"Could not parse date: {date_str}")
                                    continue
                        else:
                            date_obj = date_str  # Already a date object
                        
                        # Extract symbol based on source
                        if source_key == 'binance':
                            symbol = row['Symbol'].replace('USDT', '')
                        elif source_key == 'bitfinex':
                            symbol = row['symbol'].replace('USD', '')
                        elif source_key == 'bitstamp':
                            symbol = row['symbol'].replace('USD', '')
                        elif source_key == 'gemini':
                            symbol = row['symbol'].replace('USD', '')
                        elif source_key == 'coinlore':
                            symbol = row['Symbol']
                        else:
                            raise ValueError(f"Unknown source: {source_key}")

                        # Get asset ID
                        asset_id = self.get_or_create_asset(symbol)
                        
                        # Create asset source mapping
                        self.create_asset_source_mapping(asset_id, source_id, symbol)

                        # Extract price data
                        if source_key == 'binance':
                            open_price = row.get('Open', row.get('open'))
                            high_price = row.get('High', row.get('high'))
                            low_price = row.get('Low', row.get('low'))
                            close_price = row.get('Close', row.get('close'))
                            volume = row.get('Volume ATOM', row.get('volume_atom'))
                        elif source_key == 'coinlore':
                            # Remove $ from prices and convert to float
                            open_price = float(row['Open'].replace('$', ''))
                            high_price = float(row['High'].replace('$', ''))
                            low_price = float(row['Low'].replace('$', ''))
                            close_price = float(row['Close'].replace('$', ''))
                            volume = float(row['Volume(CELO)'].replace('?', '0'))
                        else:
                            open_price = row.get('open')
                            high_price = row.get('high')
                            low_price = row.get('low')
                            close_price = row.get('close')
                            volume = row.get('Volume ATOM', row.get('volume_atom'))

                        # Create price data record
                        price_data = PriceData(
                            asset_id=asset_id,
                            date=date_obj,
                            open=open_price,
                            high=high_price,
                            low=low_price,
                            close=close_price,
                            volume=volume,
                            source_id=source_id,
                            raw_data=json.dumps(row.to_dict(), default=date_handler),
                            confidence_score=1.0  # Default confidence score
                        )
                        
                        session.merge(price_data)
                        session.commit()
                        
                    except Exception as e:
                        print(f"Error processing row: {e}")
                        continue
                        
        except Exception as e:
            print(f"Error importing data from {file_path}: {e}")
            raise

    def migrate_all_data(self, data_dir: str = "data/historical_price_data"):
        """Migrate all CSV files in the data directory"""
        try:
            # Setup database and initialize sources
            self.setup_database()
            self.initialize_data_sources()
            
            # Process all CSV files
            for filename in os.listdir(data_dir):
                if filename.endswith('.csv'):
                    file_path = os.path.join(data_dir, filename)
                    print(f"\nProcessing {filename}...")
                    self.import_csv_data(file_path)
                    
            print("\nMigration completed successfully")
            
        except Exception as e:
            print(f"Error during migration: {e}")
            raise
        finally:
            self.close()
            
    def close(self):
        """Close database connection"""
        self.engine.dispose()

def main():
    # Delete existing database file if it exists
    db_path = "data/databases/portfolio.db"
    if os.path.exists(db_path):
        os.remove(db_path)
        print(f"Removed existing database: {db_path}")
    
    # Run migration
    migrator = DatabaseMigration(db_path)
    migrator.migrate_all_data()

if __name__ == "__main__":
    main() 