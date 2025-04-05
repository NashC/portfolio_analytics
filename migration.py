import os
import sqlite3
import pandas as pd
from datetime import datetime, date
import json
from typing import Dict, List, Optional

def date_handler(obj):
    """JSON serializer for objects not serializable by default json code"""
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    raise TypeError(f"Type {type(obj)} not serializable")

class DatabaseMigration:
    def __init__(self, db_path: str = "data/historical_price_data/prices.db"):
        self.db_path = os.path.abspath(db_path)
        self.conn = sqlite3.connect(self.db_path)
        self.cursor = self.conn.cursor()
        
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
            schema_path = os.path.join(os.path.dirname(self.db_path), '..', '..', 'schema.sql')
            print(f"Loading schema from: {schema_path}")
            with open(schema_path, 'r') as f:
                schema = f.read()
            self.cursor.executescript(schema)
            self.conn.commit()
            print("Database schema created successfully")
        except Exception as e:
            print(f"Error creating database schema: {e}")
            raise
        
    def initialize_data_sources(self):
        """Insert data sources and get their IDs"""
        try:
            for source_key, source_data in self.data_sources.items():
                self.cursor.execute("""
                    INSERT OR IGNORE INTO data_sources (name, type)
                    VALUES (?, ?)
                """, (source_data['name'], source_data['type']))
                
                self.cursor.execute("""
                    SELECT source_id FROM data_sources WHERE name = ?
                """, (source_data['name'],))
                result = self.cursor.fetchone()
                if result:
                    self.source_ids[source_key] = result[0]
                else:
                    print(f"Warning: Could not find source_id for {source_data['name']}")
                
            self.conn.commit()
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
            
            self.cursor.execute("""
                SELECT asset_id FROM assets WHERE symbol = ?
            """, (base_symbol,))
            result = self.cursor.fetchone()
            
            if result:
                return result[0]
                
            print(f"Creating new asset: {base_symbol}")
            self.cursor.execute("""
                INSERT INTO assets (symbol, type)
                VALUES (?, ?)
            """, (base_symbol, asset_type))
            self.conn.commit()
            
            self.cursor.execute("""
                SELECT asset_id FROM assets WHERE symbol = ?
            """, (base_symbol,))
            return self.cursor.fetchone()[0]
        except Exception as e:
            print(f"Error creating asset {symbol}: {e}")
            raise
        
    def create_asset_source_mapping(self, asset_id: int, source_id: int, source_symbol: str):
        """Create mapping between asset and data source"""
        try:
            self.cursor.execute("""
                INSERT OR IGNORE INTO asset_source_mappings 
                (asset_id, source_id, source_symbol)
                VALUES (?, ?, ?)
            """, (asset_id, source_id, source_symbol))
            self.conn.commit()
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
            
            # Process each row
            for _, row in df.iterrows():
                try:
                    # Extract date based on source
                    if source_key == 'binance':
                        date = row['Date']
                    elif source_key == 'coinlore':
                        # Convert MM/DD/YYYY to YYYY-MM-DD
                        date = datetime.strptime(row['Date'], '%m/%d/%Y').strftime('%Y-%m-%d')
                    else:
                        date = row['date']
                    
                    # Convert pandas Timestamp to string if needed
                    if isinstance(date, pd.Timestamp):
                        date = date.strftime('%Y-%m-%d %H:%M:%S')
                    
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

                    # Insert into database
                    self.cursor.execute("""
                        INSERT OR REPLACE INTO price_data (
                            asset_id, date, source_id, open, high, low, close, volume, last_updated
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
                    """, (asset_id, date, source_id, open_price, high_price, low_price, close_price, volume))

                except Exception as e:
                    print(f"Error processing row in {file_path}: {e}")
                    continue

            self.conn.commit()
            print(f"Successfully imported {len(df)} rows from {filename}")

        except Exception as e:
            print(f"Error processing file {file_path}: {e}")
            return
        
    def migrate_all_data(self, data_dir: str = "data/historical_price_data"):
        """Migrate all CSV files from the data directory"""
        try:
            data_dir = os.path.abspath(data_dir)
            print(f"Looking for CSV files in: {data_dir}")
            
            # Setup database and initialize sources
            self.setup_database()
            self.initialize_data_sources()
            
            # Process each CSV file
            file_count = 0
            for filename in os.listdir(data_dir):
                if filename.endswith('.csv'):
                    # Extract source from filename (e.g., "historical_price_data_daily_gemini_BTCUSD.csv")
                    for source_key in self.source_ids.keys():
                        if source_key in filename.lower():
                            print(f"\nProcessing {filename}...")
                            file_path = os.path.join(data_dir, filename)
                            self.import_csv_data(file_path)
                            file_count += 1
                            break
                    else:
                        print(f"Skipping {filename}: no matching source found")
                        
            print(f"\nProcessed {file_count} files successfully")
            
        except Exception as e:
            print(f"Error during migration: {e}")
            raise
        
    def close(self):
        """Close database connection"""
        self.conn.close()

def main():
    # Delete existing database file if it exists
    db_path = os.path.abspath("data/historical_price_data/prices.db")
    if os.path.exists(db_path):
        print(f"Deleting existing database: {db_path}")
        os.remove(db_path)
        
    migration = DatabaseMigration()
    try:
        migration.migrate_all_data()
        print("Migration completed successfully!")
    except Exception as e:
        print(f"Error during migration: {e}")
    finally:
        migration.close()

if __name__ == "__main__":
    main() 