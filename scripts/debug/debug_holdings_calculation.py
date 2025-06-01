#!/usr/bin/env python3

import pandas as pd
from datetime import datetime

def debug_holdings_calculation():
    """Debug the holdings calculation step by step."""
    
    print("=== DEBUGGING HOLDINGS CALCULATION ===")
    
    # Load and filter transactions
    df = pd.read_csv('output/transactions_normalized.csv', parse_dates=['timestamp'])
    portfolio_affecting_types = ['buy', 'sell', 'staking_reward', 'dividend', 'interest', 'deposit', 'withdrawal', 'swap']
    filtered_df = df[df['type'].isin(portfolio_affecting_types)]
    
    # Focus on ETH transactions
    eth_transactions = filtered_df[filtered_df['asset'] == 'ETH'].copy()
    print(f"ETH transactions: {len(eth_transactions)}")
    print(f"Total ETH quantity: {eth_transactions['quantity'].sum():.6f}")
    
    # Simulate the portfolio calculation logic
    asset_transactions = eth_transactions.copy()
    asset_transactions = asset_transactions.set_index('timestamp')
    
    print(f"\nAfter setting timestamp as index: {len(asset_transactions)} transactions")
    
    # Group by timestamp and sum quantities (this is where the issue might be)
    grouped = asset_transactions.groupby(asset_transactions.index)['quantity'].sum()
    print(f"After grouping by timestamp: {len(grouped)} unique dates")
    print(f"Total quantity after grouping: {grouped.sum():.6f}")
    
    # Check for any dates with multiple transactions
    duplicate_dates = asset_transactions.index[asset_transactions.index.duplicated()].unique()
    if len(duplicate_dates) > 0:
        print(f"\n⚠️ Found {len(duplicate_dates)} dates with multiple transactions:")
        for date in duplicate_dates[:5]:  # Show first 5
            same_date_txns = asset_transactions[asset_transactions.index == date]
            print(f"  {date}: {len(same_date_txns)} transactions, total quantity: {same_date_txns['quantity'].sum():.6f}")
    else:
        print("\n✅ No duplicate dates found")
    
    # Convert to DataFrame for reindexing
    asset_transactions_df = pd.DataFrame({'quantity': grouped})
    print(f"DataFrame shape after conversion: {asset_transactions_df.shape}")
    
    # Create a sample date range for testing
    start_date = eth_transactions['timestamp'].min()
    end_date = eth_transactions['timestamp'].max()
    date_range = pd.date_range(start=start_date, end=end_date, freq='D')
    print(f"Date range: {len(date_range)} days from {start_date.date()} to {end_date.date()}")
    
    # Reindex to match date range
    asset_transactions_reindexed = asset_transactions_df.reindex(date_range, method='ffill')
    print(f"After reindexing: {asset_transactions_reindexed.shape}")
    
    # Calculate cumulative holdings
    holdings = asset_transactions_reindexed['quantity'].fillna(0).cumsum()
    print(f"Final holdings shape: {holdings.shape}")
    print(f"Final ETH balance: {holdings.iloc[-1]:.6f}")
    
    # Check for any anomalies in the cumulative sum
    max_holding = holdings.max()
    min_holding = holdings.min()
    print(f"Holdings range: {min_holding:.6f} to {max_holding:.6f}")
    
    if max_holding > 1000:  # Unreasonably high
        print("⚠️ Holdings appear inflated!")
        # Find where the big jump happens
        big_jumps = holdings.diff().abs() > 10
        if big_jumps.any():
            jump_dates = holdings[big_jumps].head(5)
            print("Large jumps in holdings:")
            for date, value in jump_dates.items():
                print(f"  {date.date()}: {value:.6f}")

if __name__ == "__main__":
    debug_holdings_calculation() 