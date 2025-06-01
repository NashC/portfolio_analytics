import pandas as pd

# Load the normalized data
df = pd.read_csv('output/transactions_normalized.csv', parse_dates=['timestamp'])

print('=== DATA ANALYSIS ===')
print('Total transactions:', len(df))
print('Date range:', df['timestamp'].min(), 'to', df['timestamp'].max())

print('\n=== TRANSACTION TYPES ===')
print(df['type'].value_counts())

print('\n=== ASSETS ===')
print('Total unique assets:', df['asset'].nunique())
print('Top assets by transaction count:')
print(df['asset'].value_counts().head(10))

print('\n=== QUANTITY ANALYSIS ===')
print('Quantity stats:')
print(df['quantity'].describe())

print('\n=== LARGE TRANSACTIONS ===')
large_txns = df[df['quantity'].abs() > 1000]
print('Transactions with quantity > 1000:', len(large_txns))
if len(large_txns) > 0:
    print(large_txns[['timestamp', 'type', 'asset', 'quantity', 'price']].head(10))

print('\n=== USD TRANSACTIONS ===')
usd_txns = df[df['asset'] == 'USD']
print('USD transactions:', len(usd_txns))
print('USD quantity stats:')
print(usd_txns['quantity'].describe())

print('\n=== POTENTIAL ISSUES ===')
# Check for very large USD amounts
large_usd = usd_txns[usd_txns['quantity'].abs() > 10000]
print('USD transactions > $10,000:', len(large_usd))
if len(large_usd) > 0:
    print(large_usd[['timestamp', 'type', 'quantity', 'institution']].head(10))

# Check for duplicate transactions
duplicates = df.duplicated(subset=['timestamp', 'type', 'asset', 'quantity', 'price'])
print('Duplicate transactions:', duplicates.sum())

# Check for unrealistic prices
high_prices = df[df['price'] > 100000]
print('Transactions with price > $100,000:', len(high_prices))
if len(high_prices) > 0:
    print(high_prices[['timestamp', 'asset', 'quantity', 'price']].head(5)) 