#!/usr/bin/env python3

import pandas as pd

def analyze_portfolio_assets():
    """Analyze all assets to understand the high portfolio value."""
    
    df = pd.read_csv('output/transactions_normalized.csv', parse_dates=['timestamp'])
    
    # Apply the same filtering as the portfolio calculation
    portfolio_affecting_types = ['buy', 'sell', 'staking_reward', 'dividend', 'interest', 'deposit', 'withdrawal', 'swap']
    filtered_df = df[df['type'].isin(portfolio_affecting_types)]
    
    print('=== PORTFOLIO ASSET ANALYSIS ===')
    print(f'Total transactions (filtered): {len(filtered_df)}')
    
    # Calculate balance for each asset
    asset_balances = filtered_df.groupby('asset')['quantity'].sum().sort_values(ascending=False)
    
    print('\n=== TOP 15 ASSETS BY QUANTITY ===')
    for asset, balance in asset_balances.head(15).items():
        print(f'{asset}: {balance:.6f} units')
    
    # Estimate values for major crypto assets (rough estimates)
    crypto_prices = {
        'BTC': 65000,
        'ETH': 3500,
        'BCH': 500,
        'LTC': 85,
        'XLM': 0.12,
        'XRP': 0.60,
        'ADA': 0.50,
        'SOL': 150,
        'DOT': 7,
        'ATOM': 8,
        'LINK': 15,
        'UNI': 8,
        'AAVE': 100,
        'COMP': 60,
        'YFI': 8000,
        'FIL': 6,
        'ALGO': 0.20,
        'XTZ': 1,
        'ZEC': 30,
        'ETC': 25,
        'BAT': 0.25,
        'ZRX': 0.40,
        'REP': 15,
        'MKR': 2500,
        'SNX': 3,
        'SUSHI': 1,
        'STORJ': 0.50,
        'EOS': 1,
        'AVAX': 35,
        'MATIC': 0.50,
        'MANA': 0.40,
        'ETH2': 3500,  # Same as ETH
        'CGLD': 1,
        'GUSD': 1,
        'USDC': 1,
        'USD': 1
    }
    
    print('\n=== ESTIMATED ASSET VALUES (TOP 10) ===')
    estimated_values = []
    for asset, balance in asset_balances.items():
        if asset in crypto_prices and balance > 0:
            estimated_value = balance * crypto_prices[asset]
            estimated_values.append((asset, balance, crypto_prices[asset], estimated_value))
    
    # Sort by estimated value
    estimated_values.sort(key=lambda x: x[3], reverse=True)
    
    total_estimated_value = 0
    for asset, balance, price, value in estimated_values[:10]:
        print(f'{asset}: {balance:.6f} × ${price:,.0f} = ${value:,.2f}')
        total_estimated_value += value
    
    print(f'\nTotal estimated value (top 10): ${total_estimated_value:,.2f}')
    
    # Check for any extremely large balances
    print('\n=== ASSETS WITH LARGE BALANCES ===')
    for asset, balance in asset_balances.items():
        if balance > 1000:  # Large quantities
            print(f'{asset}: {balance:,.2f} units')

if __name__ == "__main__":
    analyze_portfolio_assets() 