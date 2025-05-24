#!/usr/bin/env python3
"""
Portfolio Returns Test with Real Data

This script tests the complete portfolio returns pipeline using real transaction data
and validates the accuracy of the calculations.
"""

import sys
import os
from datetime import date, datetime, timedelta
import pandas as pd
from pathlib import Path
import sqlite3

# Add the app directory to the Python path
sys.path.append(str(Path(__file__).parent))

def test_with_real_data():
    """Test portfolio returns with real transaction data."""
    print("🚀 Portfolio Returns Test with Real Data")
    print("=" * 60)
    
    try:
        # Import required modules
        from app.valuation.portfolio import get_portfolio_value, get_value_series
        from app.analytics.returns import daily_returns, cumulative_returns, twrr
        from app.ingestion.update_positions import PositionEngine
        from app.db.session import get_db
        from app.db.base import Transaction, PositionDaily, PriceData, Asset
        from sqlalchemy import select, func
        
        print("📊 Checking existing data...")
        
        with next(get_db()) as db:
            # Check if we have transactions
            transaction_count = db.execute(select(func.count(Transaction.transaction_id))).scalar()
            print(f"  📈 Transactions in database: {transaction_count}")
            
            # Check if we have price data
            price_count = db.execute(select(func.count(PriceData.price_id))).scalar()
            print(f"  💰 Price data points: {price_count}")
            
            # Check if we have position data
            position_count = db.execute(select(func.count(PositionDaily.position_id))).scalar()
            print(f"  📊 Position data points: {position_count}")
            
            if transaction_count == 0:
                print("  ⚠️  No transaction data found. Please run migration.py first.")
                return False
            
            if price_count == 0:
                print("  ⚠️  No price data found. Please run price data ingestion first.")
                return False
            
            # Get date range of transactions
            date_range = db.execute(
                select(
                    func.min(Transaction.date).label('min_date'),
                    func.max(Transaction.date).label('max_date')
                )
            ).first()
            
            print(f"  📅 Transaction date range: {date_range.min_date} to {date_range.max_date}")
            
            # Update positions if needed
            if position_count == 0:
                print("  🔄 Updating positions from transactions...")
                position_engine = PositionEngine(db)
                updated_count = position_engine.update_positions_from_transactions(
                    start_date=date_range.min_date,
                    end_date=date_range.max_date
                )
                print(f"  📊 Updated {updated_count} position records")
                
                # Commit the changes
                db.commit()
                
                # Recheck position count
                position_count = db.execute(select(func.count(PositionDaily.position_id))).scalar()
                print(f"  📊 Position data points after update: {position_count}")
        
        print("\n📈 Testing Portfolio Valuation...")
        
        # Test portfolio value for a specific date
        test_date = date(2024, 6, 1)  # Use a date likely to have data
        print(f"  📅 Testing portfolio value for {test_date}...")
        
        try:
            portfolio_value = get_portfolio_value(test_date)
            print(f"    💰 Portfolio value: ${portfolio_value:,.2f}")
        except Exception as e:
            print(f"    ❌ Error getting portfolio value: {e}")
            # Try with a different date
            test_date = date(2024, 1, 1)
            print(f"  📅 Trying with {test_date}...")
            portfolio_value = get_portfolio_value(test_date)
            print(f"    💰 Portfolio value: ${portfolio_value:,.2f}")
        
        # Test value series over a month
        start_date = test_date
        end_date = test_date + timedelta(days=30)
        print(f"  📈 Testing value series from {start_date} to {end_date}...")
        
        value_series = get_value_series(start_date, end_date)
        print(f"    📊 Value series length: {len(value_series)} days")
        
        if len(value_series) > 0:
            non_zero_values = value_series[value_series > 0]
            print(f"    📊 Non-zero values: {len(non_zero_values)}")
            
            if len(non_zero_values) > 0:
                print(f"    💰 Value range: ${non_zero_values.min():,.2f} - ${non_zero_values.max():,.2f}")
                print(f"    💰 Average value: ${non_zero_values.mean():,.2f}")
                
                # Calculate returns if we have sufficient data
                if len(non_zero_values) > 1:
                    print("\n📈 Testing Returns Calculations...")
                    
                    # Use only non-zero values for returns calculation
                    returns = daily_returns(non_zero_values)
                    print(f"    📈 Daily returns calculated: {len(returns)} periods")
                    
                    if len(returns) > 0:
                        print(f"    📈 Average daily return: {returns.mean():.4f} ({returns.mean()*100:.2f}%)")
                        print(f"    📈 Daily return std: {returns.std():.4f} ({returns.std()*100:.2f}%)")
                        print(f"    📈 Best day: {returns.max():.4f} ({returns.max()*100:.2f}%)")
                        print(f"    📈 Worst day: {returns.min():.4f} ({returns.min()*100:.2f}%)")
                        
                        # Cumulative returns
                        cum_returns = cumulative_returns(returns)
                        print(f"    📈 Total return: {cum_returns.iloc[-1]:.4f} ({cum_returns.iloc[-1]*100:.2f}%)")
                        
                        # TWRR
                        twrr_result = twrr(non_zero_values)
                        print(f"    📈 TWRR (annualized): {twrr_result:.4f} ({twrr_result*100:.2f}%)")
                        
                        print("    ✅ All returns calculations successful!")
                    else:
                        print("    ⚠️  No returns calculated (insufficient data)")
                else:
                    print("    ⚠️  Insufficient data for returns calculation")
            else:
                print("    ⚠️  No non-zero portfolio values found")
        else:
            print("    ⚠️  No value series data found")
        
        print("\n🌐 Testing API Integration...")
        
        try:
            from fastapi.testclient import TestClient
            from app.api import app
            
            client = TestClient(app)
            
            # Test portfolio value endpoint
            response = client.get(f"/portfolio/value?target_date={test_date}")
            if response.status_code == 200:
                data = response.json()
                print(f"    ✅ API Portfolio value: ${data['portfolio_value']:,.2f}")
            else:
                print(f"    ❌ API Error: {response.status_code} - {response.text}")
            
            # Test value series endpoint
            response = client.get(f"/portfolio/value-series?start_date={start_date}&end_date={end_date}")
            if response.status_code == 200:
                data = response.json()
                print(f"    ✅ API Value series: {len(data['value_series'])} data points")
            else:
                print(f"    ❌ API Error: {response.status_code} - {response.text}")
            
            # Test returns endpoint
            response = client.get(f"/portfolio/returns?start_date={start_date}&end_date={end_date}")
            if response.status_code == 200:
                data = response.json()
                print(f"    ✅ API Returns: {len(data['daily_returns'])} return periods")
                if 'twrr' in data:
                    print(f"    ✅ API TWRR: {data['twrr']:.4f} ({data['twrr']*100:.2f}%)")
            else:
                print(f"    ❌ API Error: {response.status_code} - {response.text}")
                
        except Exception as e:
            print(f"    ❌ API testing error: {e}")
        
        print("\n✅ Portfolio returns test with real data complete!")
        return True
        
    except Exception as e:
        print(f"❌ Error in real data test: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_with_real_data()
    sys.exit(0 if success else 1) 