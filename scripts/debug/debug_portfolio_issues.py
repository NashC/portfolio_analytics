#!/usr/bin/env python3

import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
from app.analytics.portfolio import compute_portfolio_time_series_with_external_prices, fetch_stock_prices

def debug_yfinance_issue():
    """Debug the yfinance 'scalar values' error."""
    print("=== DEBUGGING YFINANCE ISSUE ===")
    
    # Test with a simple stock symbol
    test_symbol = "AAPL"
    start_date = datetime(2024, 1, 1)
    end_date = datetime(2024, 1, 10)
    
    print(f"Testing yfinance with {test_symbol} from {start_date} to {end_date}")
    
    try:
        # Direct yfinance call
        data = yf.download(test_symbol, start=start_date, end=end_date, progress=False)
        print(f"✅ Direct yfinance call successful")
        print(f"Data shape: {data.shape}")
        print(f"Columns: {data.columns.tolist()}")
        print(f"Index type: {type(data.index)}")
        print(f"Data types: {data.dtypes}")
        
        # Test our function
        result = fetch_stock_prices(test_symbol, start_date, end_date)
        if result is not None:
            print(f"✅ Our function successful")
            print(f"Result shape: {result.shape}")
            print(f"Result columns: {result.columns.tolist()}")
        else:
            print(f"❌ Our function failed")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        print(f"Error type: {type(e)}")

def debug_duplicate_eth():
    """Debug the duplicate ETH issue in portfolio calculation."""
    print("\n=== DEBUGGING DUPLICATE ETH ISSUE ===")
    
    # Load transactions
    df = pd.read_csv('output/transactions_normalized.csv', parse_dates=['timestamp'])
    
    # Check for ETH-related assets
    eth_assets = df[df['asset'].str.contains('ETH', case=False, na=False)]['asset'].unique()
    print(f"ETH-related assets found: {eth_assets}")
    
    # Check transaction counts for each ETH asset
    for asset in eth_assets:
        count = len(df[df['asset'] == asset])
        print(f"  {asset}: {count} transactions")
    
    # Check if there are multiple ETH variants
    eth_transactions = df[df['asset'].str.contains('ETH', case=False, na=False)]
    print(f"\nETH transaction types: {eth_transactions['type'].value_counts().to_dict()}")
    print(f"ETH institutions: {eth_transactions['institution'].value_counts().to_dict()}")
    
    # Calculate portfolio to see the issue
    portfolio_ts = compute_portfolio_time_series_with_external_prices(df)
    if not portfolio_ts.empty:
        latest_values = portfolio_ts.iloc[-1].drop('total')
        eth_values = latest_values[latest_values.index.str.contains('ETH', case=False, na=False)]
        print(f"\nETH values in portfolio:")
        for asset, value in eth_values.items():
            if value > 0:
                print(f"  {asset}: ${value:,.2f}")

def debug_asset_processing():
    """Debug asset processing and filtering."""
    print("\n=== DEBUGGING ASSET PROCESSING ===")
    
    # Load transactions
    df = pd.read_csv('output/transactions_normalized.csv', parse_dates=['timestamp'])
    
    # Check all unique assets
    all_assets = df['asset'].unique()
    print(f"Total unique assets: {len(all_assets)}")
    
    # Categorize assets
    crypto_assets = []
    stock_assets = []
    options_assets = []
    stablecoin_assets = []
    other_assets = []
    
    STABLECOINS = ["USDC", "GUSD", "USD", "USDT", "DAI", "BUSD"]
    
    for asset in all_assets:
        if pd.isna(asset) or asset.strip() == '':
            continue
        asset_str = str(asset).strip()
        
        if asset_str in STABLECOINS:
            stablecoin_assets.append(asset_str)
        elif ' ' in asset_str or 'C00' in asset_str or 'P00' in asset_str:
            options_assets.append(asset_str)
        elif asset_str in ['BTC', 'ETH', 'LTC', 'BCH', 'ADA', 'SOL', 'ATOM', 'DOT', 'AVAX', 'ALGO', 'LINK', 'XRP', 'XLM', 'XTZ', 'ZEC', 'ZRX', 'BAT', 'MANA', 'MATIC', 'AAVE', 'COMP', 'UNI', 'SUSHI', 'YFI', 'MKR', 'SNX', 'STORJ', 'EOS', 'FIL', 'REP', 'CGLD', 'ETH2', 'ETC']:
            crypto_assets.append(asset_str)
        elif len(asset_str) <= 5 and asset_str.isupper():
            stock_assets.append(asset_str)
        else:
            other_assets.append(asset_str)
    
    print(f"Crypto assets ({len(crypto_assets)}): {crypto_assets}")
    print(f"Stock assets ({len(stock_assets)}): {stock_assets}")
    print(f"Options assets ({len(options_assets)}): {options_assets}")
    print(f"Stablecoin assets ({len(stablecoin_assets)}): {stablecoin_assets}")
    print(f"Other assets ({len(other_assets)}): {other_assets}")

def debug_transaction_filtering():
    """Debug transaction filtering in portfolio calculation."""
    print("\n=== DEBUGGING TRANSACTION FILTERING ===")
    
    # Load transactions
    df = pd.read_csv('output/transactions_normalized.csv', parse_dates=['timestamp'])
    
    print(f"Total transactions: {len(df)}")
    print(f"Transaction types: {df['type'].value_counts().to_dict()}")
    
    # Check what gets filtered out
    portfolio_affecting_types = [
        'buy', 'sell',           # Direct purchases and sales
        'staking_reward',        # Earned rewards (increase holdings)
        'dividend', 'interest',  # Earned income (increase holdings)
        'deposit', 'withdrawal', # Fiat deposits/withdrawals (for USD/stablecoins)
        'swap'                   # Asset conversions
    ]
    
    filtered_df = df[df['type'].isin(portfolio_affecting_types)]
    excluded_df = df[~df['type'].isin(portfolio_affecting_types)]
    
    print(f"\nAfter filtering: {len(filtered_df)} transactions")
    print(f"Excluded: {len(excluded_df)} transactions")
    print(f"Excluded types: {excluded_df['type'].value_counts().to_dict()}")

if __name__ == "__main__":
    debug_yfinance_issue()
    debug_duplicate_eth()
    debug_asset_processing()
    debug_transaction_filtering() 