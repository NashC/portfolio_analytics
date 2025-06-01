#!/usr/bin/env python3

import pandas as pd
from app.analytics.portfolio import fetch_historical_prices, compute_portfolio_time_series_with_external_prices
from datetime import datetime

def debug_price_data():
    """Debug the price data and portfolio calculation."""
    
    print("=== DEBUGGING PRICE DATA AND PORTFOLIO CALCULATION ===")
    
    # Load transactions
    df = pd.read_csv('output/transactions_normalized.csv', parse_dates=['timestamp'])
    portfolio_affecting_types = ['buy', 'sell', 'staking_reward', 'dividend', 'interest', 'deposit', 'withdrawal', 'swap']
    filtered_df = df[df['type'].isin(portfolio_affecting_types)]
    
    # Test with just ETH transactions
    eth_transactions = filtered_df[filtered_df['asset'] == 'ETH'].copy()
    print(f"ETH transactions: {len(eth_transactions)}")
    print(f"ETH balance: {eth_transactions['quantity'].sum():.6f}")
    
    # Test price fetching for ETH
    assets = ['ETH']
    start_date = datetime(2017, 1, 1)
    end_date = datetime(2025, 5, 15)
    
    print("\n=== TESTING PRICE DATA FETCHING ===")
    prices_df = fetch_historical_prices(assets, start_date, end_date)
    print(f"Price DataFrame shape: {prices_df.shape}")
    print(f"Columns: {list(prices_df.columns)}")
    print(f"ETH column count: {list(prices_df.columns).count('ETH')}")
    
    if 'ETH' in prices_df.columns:
        print(f"ETH price sample (last 5 days):")
        print(prices_df['ETH'].tail(5))
        
        # Check for duplicate columns
        duplicate_cols = prices_df.columns[prices_df.columns.duplicated()].tolist()
        if duplicate_cols:
            print(f"⚠️ DUPLICATE COLUMNS FOUND: {duplicate_cols}")
        else:
            print("✅ No duplicate columns in price data")
    
    # Test portfolio calculation with just ETH
    print("\n=== TESTING PORTFOLIO CALCULATION WITH ETH ONLY ===")
    portfolio_ts = compute_portfolio_time_series_with_external_prices(eth_transactions)
    
    if not portfolio_ts.empty:
        latest_row = portfolio_ts.iloc[-1]
        print(f"Portfolio columns: {list(portfolio_ts.columns)}")
        print(f"Latest portfolio row:")
        for col, value in latest_row.items():
            if value > 0:
                print(f"  {col}: {value:,.2f}")
        
        # Check for duplicate ETH columns in portfolio
        eth_cols = [col for col in portfolio_ts.columns if 'ETH' in col]
        print(f"ETH-related columns: {eth_cols}")

if __name__ == "__main__":
    debug_price_data() 