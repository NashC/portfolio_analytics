import pandas as pd
import datetime
from price_service import price_service

# Define the assets and date range
assets = ['FIL', 'ETH', 'LTC', 'BTC']
start_date = datetime.datetime(2024, 5, 29)
end_date = datetime.datetime(2024, 6, 20)

# Load transaction data
transactions = pd.read_csv('output/transactions_normalized.csv', parse_dates=['timestamp'])
gemini_transfers = transactions[(transactions['institution'] == 'gemini') & 
                               (transactions['type'].isin(['transfer_in', 'transfer_out']))]

print(f'Found {len(gemini_transfers)} Gemini transfer transactions')
print('\nAssets involved in transfers:')
print(gemini_transfers['asset'].unique())
print('\nDate range of transfers:')
print(f'Earliest: {gemini_transfers.timestamp.min()}')
print(f'Latest: {gemini_transfers.timestamp.max()}')

# Get pricing data from database
prices_df = price_service.get_multi_asset_prices(assets, start_date, end_date)

# Check each transfer transaction and compare hardcoded prices with database prices
print('\nComparing hardcoded prices with database prices:')
print('-' * 70)
print(f"{'Asset':<5} {'Date':<12} {'Type':<12} {'Quantity':<10} {'Hardcoded':<12} {'Database':<12} {'Diff %':<8}")
print('-' * 70)

for idx, transfer in gemini_transfers.iterrows():
    asset = transfer['asset']
    date = transfer['timestamp'].replace(tzinfo=None)
    date_str = date.strftime('%Y-%m-%d')
    txn_type = transfer['type']
    quantity = abs(float(transfer['quantity']))
    hardcoded_price = float(transfer['price']) if pd.notna(transfer['price']) else 0.0
    
    # Look for price on that specific date
    asset_price = prices_df[(prices_df['symbol'] == asset) & 
                           (pd.to_datetime(prices_df['date']).dt.strftime('%Y-%m-%d') == date_str)]
    
    if not asset_price.empty:
        db_price = float(asset_price.iloc[0]['price'])
        
        # Calculate percentage difference
        if hardcoded_price > 0:
            diff_pct = ((db_price - hardcoded_price) / hardcoded_price) * 100
        else:
            diff_pct = float('nan')
            
        print(f"{asset:<5} {date_str:<12} {txn_type:<12} {quantity:<10.6f} ${hardcoded_price:<10.2f} ${db_price:<10.2f} {diff_pct:>7.2f}%")
    else:
        print(f"{asset:<5} {date_str:<12} {txn_type:<12} {quantity:<10.6f} ${hardcoded_price:<10.2f} {'N/A':<12} {'N/A':<8}")

# Calculate aggregate statistics
print('\nAggregate price comparison by asset:')
print('-' * 60)
print(f"{'Asset':<5} {'Avg Hardcoded':<15} {'Avg Database':<15} {'Avg Diff %':<10}")
print('-' * 60)

for asset in assets:
    asset_transfers = gemini_transfers[gemini_transfers['asset'] == asset]
    
    if not asset_transfers.empty:
        hardcoded_prices = []
        db_prices = []
        
        for idx, transfer in asset_transfers.iterrows():
            date = transfer['timestamp'].replace(tzinfo=None)
            date_str = date.strftime('%Y-%m-%d')
            hardcoded_price = float(transfer['price']) if pd.notna(transfer['price']) else 0.0
            
            asset_price = prices_df[(prices_df['symbol'] == asset) & 
                                  (pd.to_datetime(prices_df['date']).dt.strftime('%Y-%m-%d') == date_str)]
            
            if not asset_price.empty and hardcoded_price > 0:
                db_price = float(asset_price.iloc[0]['price'])
                hardcoded_prices.append(hardcoded_price)
                db_prices.append(db_price)
        
        if hardcoded_prices and db_prices:
            avg_hardcoded = sum(hardcoded_prices) / len(hardcoded_prices)
            avg_db = sum(db_prices) / len(db_prices)
            avg_diff_pct = ((avg_db - avg_hardcoded) / avg_hardcoded) * 100
            
            print(f"{asset:<5} ${avg_hardcoded:<13.2f} ${avg_db:<13.2f} {avg_diff_pct:>9.2f}%")
        else:
            print(f"{asset:<5} {'N/A':<15} {'N/A':<15} {'N/A':<10}")

# Print recommendation
print('\nRecommendation based on price analysis:')
for asset in assets:
    asset_transfers = gemini_transfers[gemini_transfers['asset'] == asset]
    
    if not asset_transfers.empty:
        hardcoded_prices = []
        db_prices = []
        
        for idx, transfer in asset_transfers.iterrows():
            date = transfer['timestamp'].replace(tzinfo=None)
            date_str = date.strftime('%Y-%m-%d')
            hardcoded_price = float(transfer['price']) if pd.notna(transfer['price']) else 0.0
            
            asset_price = prices_df[(prices_df['symbol'] == asset) & 
                                  (pd.to_datetime(prices_df['date']).dt.strftime('%Y-%m-%d') == date_str)]
            
            if not asset_price.empty and hardcoded_price > 0:
                db_price = float(asset_price.iloc[0]['price'])
                hardcoded_prices.append(hardcoded_price)
                db_prices.append(db_price)
        
        if hardcoded_prices and db_prices:
            avg_hardcoded = sum(hardcoded_prices) / len(hardcoded_prices)
            avg_db = sum(db_prices) / len(db_prices)
            avg_diff_pct = ((avg_db - avg_hardcoded) / avg_hardcoded) * 100
            
            if abs(avg_diff_pct) > 10:
                print(f"{asset}: Use database prices (differs by {avg_diff_pct:.2f}% from hardcoded)")
            else:
                print(f"{asset}: Either source is acceptable (difference is only {avg_diff_pct:.2f}%)")
        else:
            print(f"{asset}: Insufficient data for comparison") 