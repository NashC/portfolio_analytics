import sqlite3
import pandas as pd
from datetime import datetime
import os

def connect_to_db():
    """Connect to the database"""
    db_path = os.path.abspath("data/historical_price_data/prices.db")
    return sqlite3.connect(db_path)

def test_queries():
    """Run various test queries to verify data import"""
    conn = connect_to_db()
    cursor = conn.cursor()
    
    try:
        # 1. Check number of assets
        cursor.execute("SELECT COUNT(*) FROM assets")
        asset_count = cursor.fetchone()[0]
        print(f"\n1. Total number of assets: {asset_count}")
        
        # 2. List all assets
        cursor.execute("SELECT symbol, type FROM assets ORDER BY symbol")
        assets = cursor.fetchall()
        print("\n2. List of assets:")
        for asset in assets:
            print(f"  - {asset[0]} ({asset[1]})")
            
        # 3. Check number of price records per asset
        cursor.execute("""
            SELECT a.symbol, COUNT(*) as record_count
            FROM price_data p
            JOIN assets a ON p.asset_id = a.asset_id
            GROUP BY a.symbol
            ORDER BY record_count DESC
        """)
        print("\n3. Number of price records per asset:")
        for asset, count in cursor.fetchall():
            print(f"  - {asset}: {count} records")
            
        # 4. Check date ranges for each asset
        cursor.execute("""
            SELECT 
                a.symbol,
                MIN(p.date) as earliest_date,
                MAX(p.date) as latest_date
            FROM price_data p
            JOIN assets a ON p.asset_id = a.asset_id
            GROUP BY a.symbol
            ORDER BY a.symbol
        """)
        print("\n4. Date ranges for each asset:")
        for asset, earliest, latest in cursor.fetchall():
            print(f"  - {asset}: {earliest} to {latest}")
            
        # 5. Check data sources and their mappings
        cursor.execute("""
            SELECT 
                ds.name as source_name,
                COUNT(DISTINCT asm.asset_id) as mapped_assets
            FROM data_sources ds
            LEFT JOIN asset_source_mappings asm ON ds.source_id = asm.source_id
            GROUP BY ds.name
        """)
        print("\n5. Data sources and their asset mappings:")
        for source, count in cursor.fetchall():
            print(f"  - {source}: {count} assets mapped")
            
        # 6. Sample price data for BTC
        cursor.execute("""
            SELECT 
                p.date,
                p.open,
                p.high,
                p.low,
                p.close,
                p.volume,
                ds.name as source
            FROM price_data p
            JOIN assets a ON p.asset_id = a.asset_id
            JOIN data_sources ds ON p.source_id = ds.source_id
            WHERE a.symbol = 'BTC'
            ORDER BY p.date DESC
            LIMIT 5
        """)
        print("\n6. Sample price data for BTC (most recent):")
        for row in cursor.fetchall():
            print(f"  - Date: {row[0]}, Open: {row[1]:.2f}, High: {row[2]:.2f}, "
                  f"Low: {row[3]:.2f}, Close: {row[4]:.2f}, Volume: {row[5]:.2f}, "
                  f"Source: {row[6]}")
            
        # 7. Check for any missing data
        cursor.execute("""
            SELECT 
                a.symbol,
                COUNT(*) as total_days,
                COUNT(DISTINCT p.date) as days_with_data
            FROM assets a
            LEFT JOIN price_data p ON a.asset_id = p.asset_id
            GROUP BY a.symbol
            HAVING total_days != days_with_data
        """)
        missing_data = cursor.fetchall()
        if missing_data:
            print("\n7. Assets with potential missing data:")
            for symbol, total, with_data in missing_data:
                print(f"  - {symbol}: {total} total days, {with_data} days with data")
        else:
            print("\n7. No missing data detected")
            
    except Exception as e:
        print(f"Error running test queries: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    test_queries() 