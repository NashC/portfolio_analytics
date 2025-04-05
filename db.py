import sqlite3
import pandas as pd
from datetime import datetime, date
from pathlib import Path

class PriceDatabase:
    def __init__(self, db_path="data/historical_price_data/prices.db"):
        """Initialize the price database."""
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        """Create the database tables if they don't exist."""
        with sqlite3.connect(self.db_path) as conn:
            # Create assets table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS assets (
                    asset_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT UNIQUE NOT NULL,
                    name TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create data_sources table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS data_sources (
                    source_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    priority INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create price_data table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS price_data (
                    price_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    asset_id INTEGER NOT NULL,
                    source_id INTEGER NOT NULL,
                    date DATE NOT NULL,
                    open REAL,
                    high REAL,
                    low REAL,
                    close REAL,
                    volume REAL,
                    confidence_score REAL DEFAULT 1.0,
                    raw_data TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (asset_id) REFERENCES assets(asset_id),
                    FOREIGN KEY (source_id) REFERENCES data_sources(source_id),
                    UNIQUE(asset_id, source_id, date)
                )
            """)
            
            # Create indices for faster queries
            conn.execute("CREATE INDEX IF NOT EXISTS idx_price_data_asset_date ON price_data(asset_id, date)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_price_data_source ON price_data(source_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_assets_symbol ON assets(symbol)")

    def get_prices(self, asset: str, start_date: date, end_date: date) -> pd.DataFrame:
        """
        Retrieve historical prices for an asset within a date range.
        
        Returns:
            DataFrame with dates as index and price as values
        """
        query = """
            SELECT p.date, p.close as price
            FROM price_data p
            JOIN assets a ON p.asset_id = a.asset_id
            WHERE a.symbol = ? AND p.date BETWEEN ? AND ?
            ORDER BY p.date
        """
        
        with sqlite3.connect(self.db_path) as conn:
            df = pd.read_sql_query(
                query,
                conn,
                params=(asset, start_date, end_date),
                parse_dates=['date']
            )
            if not df.empty:
                df.set_index('date', inplace=True)
                df.index = pd.DatetimeIndex(df.index)
                return df
            return None

    def save_prices(self, asset: str, prices: pd.DataFrame, source: str):
        """
        Save historical prices for an asset.
        
        Args:
            asset: Asset symbol
            prices: DataFrame with dates as index and price as values
            source: Data source (e.g., 'coingecko', 'yfinance', 'transaction')
        """
        if prices is None or prices.empty:
            return
            
        # Prepare data for insertion
        prices = prices.reset_index()
        prices.columns = ['date', 'close']
        
        with sqlite3.connect(self.db_path) as conn:
            # Get or create asset_id
            cursor = conn.cursor()
            cursor.execute("SELECT asset_id FROM assets WHERE symbol = ?", (asset,))
            result = cursor.fetchone()
            if result:
                asset_id = result[0]
            else:
                cursor.execute("INSERT INTO assets (symbol) VALUES (?)", (asset,))
                asset_id = cursor.lastrowid
                
            # Get or create source_id
            cursor.execute("SELECT source_id FROM data_sources WHERE name = ?", (source,))
            result = cursor.fetchone()
            if result:
                source_id = result[0]
            else:
                cursor.execute("INSERT INTO data_sources (name) VALUES (?)", (source,))
                source_id = cursor.lastrowid
                
            # Insert price data
            for _, row in prices.iterrows():
                cursor.execute("""
                    INSERT OR REPLACE INTO price_data 
                    (asset_id, source_id, date, close, created_at)
                    VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                """, (asset_id, source_id, row['date'], row['close']))
            
            conn.commit()

    def get_last_updated(self, asset: str) -> datetime:
        """Get the last update timestamp for an asset."""
        query = """
            SELECT MAX(p.created_at)
            FROM price_data p
            JOIN assets a ON p.asset_id = a.asset_id
            WHERE a.symbol = ?
        """
        
        with sqlite3.connect(self.db_path) as conn:
            result = conn.execute(query, (asset,)).fetchone()[0]
            return datetime.fromisoformat(result) if result else None

    def needs_update(self, asset: str, max_age_days: int = 1) -> bool:
        """Check if the asset's price data needs updating."""
        last_updated = self.get_last_updated(asset)
        if last_updated is None:
            return True
        age = datetime.now() - last_updated
        return age.days >= max_age_days

    def get_missing_dates(self, asset: str, start_date: date, end_date: date) -> list:
        """Get list of dates missing from the database for an asset."""
        query = """
            WITH RECURSIVE dates(date) AS (
                SELECT ?
                UNION ALL
                SELECT date(date, '+1 day')
                FROM dates
                WHERE date < ?
            )
            SELECT dates.date
            FROM dates
            LEFT JOIN price_data p ON dates.date = p.date 
            JOIN assets a ON p.asset_id = a.asset_id
            WHERE a.symbol = ? AND p.close IS NULL
        """
        
        with sqlite3.connect(self.db_path) as conn:
            df = pd.read_sql_query(
                query,
                conn,
                params=(start_date, end_date, asset),
                parse_dates=['date']
            )
            return df['date'].tolist() if not df.empty else [] 