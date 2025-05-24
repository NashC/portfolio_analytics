import pandas as pd
import json
import ast

# Check tax lots for Gemini transactions
tax_lots_2024 = pd.read_csv('output/tax_lots_2024.csv')
gemini_lots = tax_lots_2024[tax_lots_2024['acquisition_exchange'] == 'gemini']
print(f'Number of Gemini acquisition lots in 2024: {len(gemini_lots)}')
if len(gemini_lots) > 0:
    print("Sample Gemini tax lots:")
    print(gemini_lots[['asset', 'quantity', 'acquisition_date', 'acquisition_exchange']].head())

# Check for current holdings (tax lots without disposal dates)
print("\nChecking for current holdings (tax lots without disposal dates):")
tax_lots_2024['disposal_date'] = pd.to_datetime(tax_lots_2024['disposal_date'], errors='coerce')
current_holdings = tax_lots_2024[tax_lots_2024['disposal_date'].isna()]
if len(current_holdings) > 0:
    print(f"Found {len(current_holdings)} current holdings (tax lots without disposal dates)")
    print("\nAssets in current holdings:")
    print(current_holdings['asset'].value_counts())
else:
    print("No current holdings found in tax_lots_2024.csv (all lots have disposal dates)")

# Check tax lots for 2025
try:
    tax_lots_2025 = pd.read_csv('output/tax_lots_2025.csv')
    gemini_lots_2025 = tax_lots_2025[tax_lots_2025['acquisition_exchange'] == 'gemini']
    print(f'\nNumber of Gemini acquisition lots in 2025: {len(gemini_lots_2025)}')
    
    # Check for current holdings in 2025 file
    tax_lots_2025['disposal_date'] = pd.to_datetime(tax_lots_2025['disposal_date'], errors='coerce')
    current_holdings_2025 = tax_lots_2025[tax_lots_2025['disposal_date'].isna()]
    if len(current_holdings_2025) > 0:
        print(f"Found {len(current_holdings_2025)} current holdings in 2025 tax lots")
        print("\nAssets in 2025 current holdings:")
        print(current_holdings_2025['asset'].value_counts())
        
        # Check if Gemini assets are in current holdings
        gemini_assets = ['FIL', 'ETH', 'LTC', 'BTC']
        gemini_holdings = current_holdings_2025[current_holdings_2025['asset'].isin(gemini_assets)]
        print(f"\nFound {len(gemini_holdings)} tax lots for Gemini assets in current holdings")
        if len(gemini_holdings) > 0:
            print(gemini_holdings[['asset', 'quantity', 'acquisition_date', 'acquisition_exchange']].head(10))
except FileNotFoundError:
    print("\nNo tax_lots_2025.csv file found")

# Check normalized transactions for Gemini
transactions = pd.read_csv('output/transactions_normalized.csv')
# Print column names to identify the right transaction type column
print("\nTransaction columns:")
print(transactions.columns.tolist())

transactions['date'] = pd.to_datetime(transactions['timestamp']).dt.strftime('%Y-%m-%d')
gemini_txns = transactions[transactions['institution'] == 'gemini']
gemini_2024 = gemini_txns[gemini_txns['date'].str.startswith('2024')]

print(f"\nTotal Gemini transactions: {len(gemini_txns)}")
print(f"Gemini transactions in 2024: {len(gemini_2024)}")

print("\nGemini 2024 transactions by asset:")
print(gemini_2024['asset'].value_counts())

# Use the correct column name for transaction types
if 'type' in transactions.columns:
    print("\nGemini 2024 transactions by type:")
    print(gemini_2024['type'].value_counts())
elif 'tx_type' in transactions.columns:
    print("\nGemini 2024 transactions by tx_type:")
    print(gemini_2024['tx_type'].value_counts())

# Let's also examine a sample of the Gemini transactions
print("\nSample of 2024 Gemini transactions:")
print(gemini_2024.head(3).to_string())

# Calculate net holdings from Gemini 2024 transactions
print("\nCalculating net holdings from Gemini 2024 transactions:")
net_holdings = {}
for _, row in gemini_2024.iterrows():
    asset = row['asset']
    quantity = row['quantity']
    if asset not in net_holdings:
        net_holdings[asset] = 0
    net_holdings[asset] += quantity

for asset, quantity in net_holdings.items():
    print(f"{asset}: {quantity}")

# Check if these assets show up in performance reports
try:
    perf_report = pd.read_csv('output/performance_report_YTD.csv')
    print("\nPerformance report YTD:")
    print(perf_report)
    
    # Parse and display the current allocation
    if 'current_allocation' in perf_report.columns:
        print("\nCurrent allocation details:")
        allocation_str = perf_report.iloc[0]['current_allocation']
        
        # Try different methods to parse the allocation string
        try:
            # Method 1: Using json.loads
            allocation = json.loads(allocation_str.replace("'", "\""))
        except:
            try:
                # Method 2: Using ast.literal_eval
                allocation = ast.literal_eval(allocation_str)
            except:
                # Method 3: Simple string parsing
                allocation = {}
                pairs = allocation_str.strip('{}').split(', ')
                for pair in pairs:
                    if ':' in pair:
                        key, value = pair.split(':', 1)
                        key = key.strip().strip("'\"")
                        value = float(value.strip())
                        allocation[key] = value
        
        # Check if Gemini assets are in the current allocation
        gemini_assets = ['FIL', 'ETH', 'LTC', 'BTC']
        print("\nGemini assets in current allocation:")
        for asset in gemini_assets:
            if asset in allocation:
                print(f"{asset}: {allocation[asset]}")
            else:
                print(f"{asset}: Not found in allocation")
                
        # Display assets with non-zero allocation
        print("\nAssets with non-zero allocation:")
        non_zero = {k: v for k, v in allocation.items() if v > 0}
        for asset, value in sorted(non_zero.items(), key=lambda x: x[1], reverse=True):
            print(f"{asset}: {value}")
except FileNotFoundError:
    print("\nNo performance_report_YTD.csv file found") 