#!/usr/bin/env python3
"""
Simple Portfolio Returns Test

This script tests the portfolio returns functionality by creating the missing
position_daily table and implementing a basic position tracking system.
"""

import sys
import os
from datetime import date, datetime, timedelta
import pandas as pd
from pathlib import Path
import sqlite3

# Add the app directory to the Python path
sys.path.append(str(Path(__file__).parent))

def setup_position_tracking():
    """Set up the position_daily table and populate it with basic data."""
    print("🔧 Setting up position tracking system...")
    
    try:
        # Connect to database
        conn = sqlite3.connect('portfolio.db')
        cursor = conn.cursor()
        
        # Check if we have any existing tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        print(f"  📊 Existing tables: {[t[0] for t in tables]}")
        
        # Create position_daily table if it doesn't exist
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS position_daily (
                position_id INTEGER PRIMARY KEY AUTOINCREMENT,
                date DATE NOT NULL,
                account_id INTEGER,
                asset_id INTEGER,
                quantity DECIMAL(20, 8) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(date, account_id, asset_id)
            )
        """)
        
        # Create a simple assets table if it doesn't exist
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS assets (
                asset_id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol VARCHAR(20) NOT NULL UNIQUE,
                name VARCHAR(100),
                asset_type VARCHAR(20) DEFAULT 'crypto'
            )
        """)
        
        # Create accounts table if it doesn't exist
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS accounts (
                account_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name VARCHAR(100) NOT NULL,
                exchange VARCHAR(50),
                account_type VARCHAR(20) DEFAULT 'trading'
            )
        """)
        
        # Create price_data table if it doesn't exist
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS price_data (
                price_id INTEGER PRIMARY KEY AUTOINCREMENT,
                asset_id INTEGER,
                date DATE NOT NULL,
                open DECIMAL(20, 8),
                high DECIMAL(20, 8),
                low DECIMAL(20, 8),
                close DECIMAL(20, 8) NOT NULL,
                volume DECIMAL(20, 8),
                source_id INTEGER DEFAULT 1,
                UNIQUE(asset_id, date, source_id)
            )
        """)
        
        # Insert sample assets
        sample_assets = [
            ('BTC', 'Bitcoin'),
            ('ETH', 'Ethereum'),
            ('USDC', 'USD Coin'),
            ('USDT', 'Tether'),
            ('SOL', 'Solana'),
            ('MATIC', 'Polygon')
        ]
        
        for symbol, name in sample_assets:
            cursor.execute("""
                INSERT OR IGNORE INTO assets (symbol, name) VALUES (?, ?)
            """, (symbol, name))
        
        # Insert sample account
        cursor.execute("""
            INSERT OR IGNORE INTO accounts (account_id, name, exchange) VALUES (1, 'Main Portfolio', 'mixed')
        """)
        
        # Insert sample price data for testing (multiple days)
        test_dates = [
            date(2024, 1, 1),
            date(2024, 1, 2),
            date(2024, 1, 3)
        ]
        
        sample_prices = [
            # Day 1 prices
            (1, test_dates[0], 42000.0),  # BTC
            (2, test_dates[0], 2500.0),   # ETH
            (3, test_dates[0], 1.0),      # USDC
            (4, test_dates[0], 1.0),      # USDT
            (5, test_dates[0], 100.0),    # SOL
            (6, test_dates[0], 0.8),      # MATIC
            # Day 2 prices (slight increase)
            (1, test_dates[1], 43000.0),  # BTC +2.38%
            (2, test_dates[1], 2550.0),   # ETH +2.0%
            (3, test_dates[1], 1.0),      # USDC
            (4, test_dates[1], 1.0),      # USDT
            (5, test_dates[1], 102.0),    # SOL +2.0%
            (6, test_dates[1], 0.82),     # MATIC +2.5%
            # Day 3 prices (slight decrease)
            (1, test_dates[2], 42500.0),  # BTC -1.16%
            (2, test_dates[2], 2525.0),   # ETH -0.98%
            (3, test_dates[2], 1.0),      # USDC
            (4, test_dates[2], 1.0),      # USDT
            (5, test_dates[2], 101.0),    # SOL -0.98%
            (6, test_dates[2], 0.81),     # MATIC -1.22%
        ]
        
        for asset_id, price_date, price in sample_prices:
            cursor.execute("""
                INSERT OR IGNORE INTO price_data (asset_id, date, close) VALUES (?, ?, ?)
            """, (asset_id, price_date, price))
        
        # Insert sample positions for all test dates
        sample_positions = [
            # Day 1 positions
            (test_dates[0], 1, 1, 0.5),    # 0.5 BTC
            (test_dates[0], 1, 2, 10.0),   # 10 ETH
            (test_dates[0], 1, 3, 1000.0), # 1000 USDC
            (test_dates[0], 1, 5, 50.0),   # 50 SOL
            # Day 2 positions (same)
            (test_dates[1], 1, 1, 0.5),    # 0.5 BTC
            (test_dates[1], 1, 2, 10.0),   # 10 ETH
            (test_dates[1], 1, 3, 1000.0), # 1000 USDC
            (test_dates[1], 1, 5, 50.0),   # 50 SOL
            # Day 3 positions (same)
            (test_dates[2], 1, 1, 0.5),    # 0.5 BTC
            (test_dates[2], 1, 2, 10.0),   # 10 ETH
            (test_dates[2], 1, 3, 1000.0), # 1000 USDC
            (test_dates[2], 1, 5, 50.0),   # 50 SOL
        ]
        
        for pos_date, account_id, asset_id, quantity in sample_positions:
            cursor.execute("""
                INSERT OR IGNORE INTO position_daily (date, account_id, asset_id, quantity) 
                VALUES (?, ?, ?, ?)
            """, (pos_date, account_id, asset_id, quantity))
        
        conn.commit()
        conn.close()
        
        print("✅ Position tracking system setup complete!")
        return True
        
    except Exception as e:
        print(f"❌ Error setting up position tracking: {e}")
        return False

def test_portfolio_functions():
    """Test the portfolio valuation functions with the new setup."""
    print("\n📊 Testing Portfolio Functions...")
    
    try:
        from app.valuation.portfolio import get_portfolio_value, get_value_series
        from app.analytics.returns import daily_returns, cumulative_returns, twrr
        
        # Test single date portfolio value
        test_date = date(2024, 1, 1)
        print(f"  📅 Testing portfolio value for {test_date}...")
        
        portfolio_value = get_portfolio_value(test_date)
        print(f"    💰 Portfolio value: ${portfolio_value:,.2f}")
        
        # Test value series (3-day range with price changes)
        start_date = date(2024, 1, 1)
        end_date = date(2024, 1, 3)
        print(f"  📈 Testing value series from {start_date} to {end_date}...")
        
        value_series = get_value_series(start_date, end_date)
        print(f"    📊 Value series length: {len(value_series)} days")
        print(f"    📊 Value series type: {type(value_series)}")
        print(f"    📊 Value series dtype: {value_series.dtype}")
        
        if len(value_series) > 0:
            print(f"    💰 Values: {value_series.tolist()}")
            
            # Verify we have numeric data
            if pd.api.types.is_numeric_dtype(value_series):
                print("    ✅ Value series contains numeric data")
                
                # Calculate returns if we have multiple days
                if len(value_series) > 1:
                    print("  📈 Testing returns calculations...")
                    
                    # Daily returns
                    returns = daily_returns(value_series)
                    print(f"    📈 Daily returns: {returns.tolist()}")
                    
                    # Cumulative returns
                    cum_returns = cumulative_returns(returns)
                    print(f"    📈 Cumulative returns: {cum_returns.tolist()}")
                    
                    # TWRR (Time-weighted rate of return)
                    twrr_result = twrr(value_series)
                    print(f"    📈 TWRR (annualized): {twrr_result:.4f} ({twrr_result*100:.2f}%)")
                    
                    print("    ✅ All returns calculations successful!")
                else:
                    print("    ⚠️  Only one data point, cannot calculate returns")
            else:
                print(f"    ❌ Value series contains non-numeric data: {value_series.dtype}")
                return False
        
        return True
        
    except Exception as e:
        print(f"    ❌ Error testing portfolio functions: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_api_endpoints():
    """Test API endpoints with the new setup."""
    print("\n🌐 Testing API Endpoints...")
    
    try:
        from fastapi.testclient import TestClient
        from app.api import app
        
        client = TestClient(app)
        
        # Test health endpoint
        print("  🏥 Testing health endpoint...")
        response = client.get("/health")
        print(f"    ✅ Health: {response.status_code}")
        
        # Test portfolio value endpoint
        print("  💰 Testing portfolio value endpoint...")
        response = client.get("/portfolio/value?target_date=2024-01-01")
        if response.status_code == 200:
            data = response.json()
            print(f"    ✅ Portfolio value: ${data['portfolio_value']:,.2f}")
        else:
            print(f"    ❌ Error: {response.status_code} - {response.text}")
        
        return True
        
    except Exception as e:
        print(f"    ❌ Error testing API: {e}")
        return False

def main():
    """Main test function."""
    print("🚀 Simple Portfolio Returns Test")
    print("="*50)
    
    # Step 1: Setup position tracking
    if not setup_position_tracking():
        print("❌ Setup failed. Exiting.")
        return
    
    # Step 2: Test portfolio functions
    if not test_portfolio_functions():
        print("❌ Portfolio function tests failed.")
    
    # Step 3: Test API endpoints
    if not test_api_endpoints():
        print("❌ API tests failed.")
    
    print("\n✅ Simple portfolio test complete!")

if __name__ == "__main__":
    main() 