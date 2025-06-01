#!/usr/bin/env python3

import pandas as pd

def analyze_filtered_eth_balance():
    """Analyze ETH balance after filtering out transfers."""
    
    df = pd.read_csv('output/transactions_normalized.csv', parse_dates=['timestamp'])

    # Apply the same filtering as the portfolio calculation
    portfolio_affecting_types = ['buy', 'sell', 'staking_reward', 'dividend', 'interest', 'deposit', 'withdrawal', 'swap']
    filtered_df = df[df['type'].isin(portfolio_affecting_types)]

    eth_transactions = filtered_df[filtered_df['asset'] == 'ETH'].copy()
    eth_transactions = eth_transactions.sort_values('timestamp')

    print('=== ETH BALANCE AFTER FILTERING OUT TRANSFERS ===')
    print(f'Total ETH transactions (filtered): {len(eth_transactions)}')

    # Calculate running balance
    eth_transactions['running_balance'] = eth_transactions['quantity'].cumsum()

    print('\nETH transaction summary by type (filtered):')
    type_summary = eth_transactions.groupby('type')['quantity'].agg(['count', 'sum']).round(6)
    print(type_summary)

    final_balance = eth_transactions['running_balance'].iloc[-1]
    print(f'\nFinal ETH balance (filtered): {final_balance:.6f}')
    print(f'At $3500/ETH, this equals: ${final_balance * 3500:,.2f}')
    
    print('\nLargest ETH transactions (filtered):')
    large_eth = eth_transactions[abs(eth_transactions['quantity']) > 1][['timestamp', 'type', 'quantity', 'running_balance']]
    print(large_eth.head(15))
    
    print('\nSwap transactions analysis:')
    swaps = eth_transactions[eth_transactions['type'] == 'swap']
    if not swaps.empty:
        print(f'Total swap quantity: {swaps["quantity"].sum():.6f} ETH')
        print('Swap details:')
        print(swaps[['timestamp', 'quantity', 'price']].head(10))
    else:
        print('No swap transactions found')

if __name__ == "__main__":
    analyze_filtered_eth_balance() 