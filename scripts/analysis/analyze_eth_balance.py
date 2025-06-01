#!/usr/bin/env python3

import pandas as pd

def analyze_eth_balance():
    """Analyze ETH transactions to understand the high portfolio value."""
    
    df = pd.read_csv('output/transactions_normalized.csv', parse_dates=['timestamp'])
    eth_transactions = df[df['asset'] == 'ETH'].copy()
    eth_transactions = eth_transactions.sort_values('timestamp')

    print('=== ETH BALANCE ANALYSIS ===')
    print(f'Total ETH transactions: {len(eth_transactions)}')

    # Calculate running balance
    eth_transactions['running_balance'] = eth_transactions['quantity'].cumsum()

    print('\nETH transaction summary by type:')
    type_summary = eth_transactions.groupby('type')['quantity'].agg(['count', 'sum']).round(6)
    print(type_summary)

    print('\nFinal ETH balance:', eth_transactions['running_balance'].iloc[-1])

    print('\nLast 10 ETH transactions:')
    last_10 = eth_transactions[['timestamp', 'type', 'quantity', 'running_balance']].tail(10)
    print(last_10)

    print('\nLargest ETH transactions:')
    large_eth = eth_transactions[abs(eth_transactions['quantity']) > 1][['timestamp', 'type', 'quantity', 'running_balance']]
    print(large_eth.head(15))
    
    print('\nStaking rewards analysis:')
    staking_rewards = eth_transactions[eth_transactions['type'] == 'staking_reward']
    print(f'Total staking rewards: {staking_rewards["quantity"].sum():.6f} ETH')
    print(f'Staking rewards count: {len(staking_rewards)}')
    print(f'Date range: {staking_rewards["timestamp"].min()} to {staking_rewards["timestamp"].max()}')
    
    print('\nTransfer out analysis:')
    transfers_out = eth_transactions[eth_transactions['type'] == 'transfer_out']
    print(f'Total transfers out: {transfers_out["quantity"].sum():.6f} ETH')
    print(f'Transfer out count: {len(transfers_out)}')
    
    print('\nWithdrawals analysis:')
    withdrawals = eth_transactions[eth_transactions['type'] == 'withdrawal']
    print(f'Total withdrawals: {withdrawals["quantity"].sum():.6f} ETH')
    print(f'Withdrawal count: {len(withdrawals)}')

if __name__ == "__main__":
    analyze_eth_balance() 