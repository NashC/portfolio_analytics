import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime, date, timedelta
import os
from typing import Optional, List, Dict, Union, Tuple
from database import Database

class PriceService:
    def __init__(self):
        """Initialize the price service with connection to the historical price database"""
        self.db_path = os.path.abspath("data/historical_price_data/prices.db")
        self.db = Database()
        # Add mapping for CELO to CGLD (since price data is stored under CELO)
        self.asset_mapping = {
            "CGLD": "CELO",  # When querying database, map CGLD to CELO
            "ETH2": "ETH",   # ETH2 uses ETH price
        }
        self.stablecoins = {'USD', 'USDC', 'USDT', 'DAI'}
        
    def __del__(self):
        if hasattr(self, 'db'):
            self.db.close()
        
    def _connect(self) -> sqlite3.Connection:
        """Create a database connection"""
        return sqlite3.connect(self.db_path)
        
    def _normalize_asset(self, asset: str) -> str:
        """Normalize asset symbol to standard format"""
        # Remove any trailing slashes
        asset = asset.rstrip("/")
        # Convert to uppercase
        asset = asset.upper()
        # Apply asset mapping if exists
        return self.asset_mapping.get(asset, asset)
        
    def get_price(self, asset: str, date_: Union[date, datetime]) -> Optional[float]:
        """Get the closing price for an asset on a specific date"""
        if isinstance(date_, datetime):
            date_ = date_.date()
            
        conn = self._connect()
        try:
            query = """
                SELECT p.close
                FROM price_data p
                JOIN assets a ON p.asset_id = a.asset_id
                WHERE a.symbol = ? AND p.date = ?
                ORDER BY p.confidence_score DESC
                LIMIT 1
            """
            cursor = conn.cursor()
            cursor.execute(query, (self._normalize_asset(asset).replace("/", ""), date_.isoformat()))
            result = cursor.fetchone()
            return result[0] if result else None
        finally:
            conn.close()
            
    def get_price_range(self, asset: str, start_date: Union[date, datetime], 
                       end_date: Union[date, datetime]) -> pd.DataFrame:
        """Get daily closing prices for an asset over a date range"""
        if isinstance(start_date, datetime):
            start_date = start_date.date()
        if isinstance(end_date, datetime):
            end_date = end_date.date()
            
        conn = self._connect()
        try:
            query = """
                SELECT p.date, p.close
                FROM price_data p
                JOIN assets a ON p.asset_id = a.asset_id
                WHERE a.symbol = ? 
                AND p.date BETWEEN ? AND ?
                ORDER BY p.date
            """
            df = pd.read_sql_query(
                query, 
                conn,
                params=(self._normalize_asset(asset).replace("/", ""), start_date.isoformat(), end_date.isoformat())
            )
            if not df.empty:
                df['date'] = pd.to_datetime(df['date'])
                df = df.set_index('date')
                df.columns = [self._normalize_asset(asset)]
            return df
        finally:
            conn.close()
            
    def get_multi_asset_prices(self, symbols: List[str], start_date: Optional[datetime] = None, end_date: Optional[datetime] = None) -> pd.DataFrame:
        """
        Get historical prices for multiple assets
        """
        # Clean and normalize symbols
        cleaned_symbols = []
        symbol_mapping = {}  # Keep track of original to normalized mapping
        for symbol in symbols:
            # Remove any trailing /USD and clean the symbol
            clean_symbol = self._normalize_asset(symbol.split('/')[0])
            cleaned_symbols.append(clean_symbol)
            symbol_mapping[clean_symbol] = symbol  # Store mapping
        
        if not cleaned_symbols:
            return pd.DataFrame(columns=['date', 'symbol', 'price'])
        
        # Handle stablecoins
        prices_list = []
        for normalized_symbol in cleaned_symbols:
            if normalized_symbol in self.stablecoins:
                # Create a date range for the stablecoin
                if start_date and end_date:
                    date_range = pd.date_range(start=start_date, end=end_date, freq='D')
                else:
                    # Default to last 30 days if no dates specified
                    end_date = datetime.now()
                    start_date = end_date - timedelta(days=30)
                    date_range = pd.date_range(start=start_date, end=end_date, freq='D')
                
                # Create a DataFrame with price of 1 for all dates
                stablecoin_prices = pd.DataFrame({
                    'date': date_range,
                    'symbol': symbol_mapping.get(normalized_symbol, normalized_symbol),  # Use original symbol
                    'price': 1.0
                })
                prices_list.append(stablecoin_prices)
            else:
                # Query the database for non-stablecoin prices
                query = """
                    SELECT 
                        DATE(p.date) as date,
                        ? as symbol,  -- Use placeholder for symbol
                        p.close as price,
                        p.confidence_score
                    FROM price_data p
                    JOIN assets a ON p.asset_id = a.asset_id
                    WHERE a.symbol = ?
                """
                params = [symbol_mapping.get(normalized_symbol, normalized_symbol), normalized_symbol]  # Use original symbol for display, normalized for query
                
                if start_date:
                    query += " AND DATE(p.date) >= DATE(?)"
                    params.append(start_date.strftime('%Y-%m-%d'))
                if end_date:
                    query += " AND DATE(p.date) <= DATE(?)"
                    params.append(end_date.strftime('%Y-%m-%d'))
                
                query += " ORDER BY p.date, p.confidence_score DESC"
                
                conn = self._connect()
                try:
                    df = pd.read_sql_query(query, conn, params=tuple(params))
                    if not df.empty:
                        df['date'] = pd.to_datetime(df['date'])
                        # Take the price with highest confidence score for each date
                        df = df.sort_values('confidence_score', ascending=False).groupby(['date', 'symbol']).first().reset_index()
                        df = df.drop('confidence_score', axis=1)
                        prices_list.append(df)
                    else:
                        # Check if the asset exists in the database
                        check_query = "SELECT COUNT(*) FROM assets WHERE symbol = ?"
                        cursor = conn.cursor()
                        cursor.execute(check_query, (normalized_symbol,))
                        count = cursor.fetchone()[0]
                        if count == 0:
                            print(f"Debug: Asset {normalized_symbol} not found in database")
                        else:
                            print(f"Debug: No price data found for {normalized_symbol} in the specified date range")
                finally:
                    conn.close()
        
        if not prices_list:
            return pd.DataFrame(columns=['date', 'symbol', 'price'])
        
        # Combine all price data
        result = pd.concat(prices_list, ignore_index=True)
        
        # Debug prints
        print("\nDebug: Result DataFrame before deduplication:")
        print(result.head())
        print("\nDebug: Result DataFrame info:")
        print(result.info())
        print("\nDebug: Checking for duplicate date-symbol combinations:")
        print(result.groupby(['date', 'symbol']).size().reset_index(name='count').query('count > 1'))
        
        # Drop duplicates, keeping the first occurrence (which has the highest confidence score)
        result = result.drop_duplicates(subset=['date', 'symbol'], keep='first')
        
        print("\nDebug: After dropping duplicates:")
        print(result.groupby(['date', 'symbol']).size().reset_index(name='count').query('count > 1'))
        
        return result
    
    def get_source_priority(self, asset: str) -> List[str]:
        """Get the priority order of data sources for an asset"""
        conn = self._connect()
        try:
            query = """
                SELECT DISTINCT ds.name
                FROM data_sources ds
                JOIN price_data p ON ds.source_id = p.source_id
                JOIN assets a ON p.asset_id = a.asset_id
                WHERE a.symbol = ?
                ORDER BY ds.priority DESC
            """
            cursor = conn.cursor()
            cursor.execute(query, (self._normalize_asset(asset).replace("/", ""),))
            return [row[0] for row in cursor.fetchall()]
        finally:
            conn.close()
            
    def get_asset_coverage(self) -> Dict[str, Dict]:
        """Get coverage information for all assets"""
        conn = self._connect()
        try:
            query = """
                SELECT 
                    a.symbol,
                    MIN(p.date) as earliest_date,
                    MAX(p.date) as latest_date,
                    COUNT(DISTINCT p.date) as days_with_data,
                    COUNT(DISTINCT p.source_id) as source_count
                FROM assets a
                JOIN price_data p ON a.asset_id = p.asset_id
                GROUP BY a.symbol
            """
            df = pd.read_sql_query(query, conn)
            
            coverage = {}
            for _, row in df.iterrows():
                coverage[row['symbol']] = {
                    'earliest_date': row['earliest_date'],
                    'latest_date': row['latest_date'],
                    'days_with_data': row['days_with_data'],
                    'source_count': row['source_count']
                }
            return coverage
        finally:
            conn.close()
            
    def validate_price_data(self, asset: str, start_date: Union[date, datetime],
                          end_date: Union[date, datetime]) -> Dict:
        """Validate price data quality for an asset in a date range"""
        if isinstance(start_date, datetime):
            start_date = start_date.date()
        if isinstance(end_date, datetime):
            end_date = end_date.date()
            
        conn = self._connect()
        try:
            query = """
                SELECT 
                    COUNT(DISTINCT p.date) as days_with_data,
                    MIN(p.close) as min_price,
                    MAX(p.close) as max_price,
                    AVG(p.close) as avg_price,
                    AVG(p.confidence_score) as avg_confidence
                FROM price_data p
                JOIN assets a ON p.asset_id = a.asset_id
                WHERE a.symbol = ?
                AND p.date BETWEEN ? AND ?
            """
            cursor = conn.cursor()
            cursor.execute(query, (self._normalize_asset(asset).replace("/", ""), 
                                 start_date.isoformat(), 
                                 end_date.isoformat()))
            row = cursor.fetchone()
            
            if row:
                return {
                    'days_with_data': row[0],
                    'min_price': row[1],
                    'max_price': row[2],
                    'avg_price': row[3],
                    'avg_confidence': row[4],
                    'expected_days': (end_date - start_date).days + 1,
                    'coverage_percent': row[0] / ((end_date - start_date).days + 1) * 100
                }
            return None
        finally:
            conn.close()

# Global instance
price_service = PriceService() 