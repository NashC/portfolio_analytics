import pandas as pd
import os

def test_2024_gemini_transactions():
    # Path to the Gemini transaction history file
    file_path = os.path.join("data", "transaction_history", "gemini_transaction_history.csv")
    
    if not os.path.exists(file_path):
        print(f"Error: File not found at {file_path}")
        return
    
    # Read the CSV file
    print(f"Reading file: {file_path}")
    df = pd.read_csv(file_path)
    
    # Check the 'Date' column format
    print(f"Date column format examples: {df['Date'].head(3).tolist()}")
    
    # Check if there are any transactions from 2024
    year_2024_mask = df['Date'].fillna('').str.startswith('2024-')
    year_2024_count = year_2024_mask.sum()
    
    print(f"Found {year_2024_count} transactions from 2024")
    
    if year_2024_count > 0:
        # Display a few examples of 2024 transactions
        df_2024 = df[year_2024_mask]
        print("\nSample 2024 transactions:")
        for i, row in df_2024.head(3).iterrows():
            print(f"Date: {row['Date']}, Type: {row['Type']}, Specification: {row['Specification']}")
        
        # Get all asset columns
        asset_cols = [col for col in df.columns if " Amount " in col and "Balance" not in col and "USD" not in col]
        assets = [col.split(" Amount ")[0] for col in asset_cols]
        print(f"\nAsset columns: {assets}")
        
        # Check each asset for 2024 transactions
        for asset in assets:
            amount_col = f"{asset} Amount {asset}"
            df_asset_2024 = df_2024[df_2024[amount_col].notna() & (df_2024[amount_col] != 0)]
            if not df_asset_2024.empty:
                print(f"\nFound {len(df_asset_2024)} {asset} transactions in 2024")
                print(f"Sample values: {df_asset_2024[amount_col].head(3).tolist()}")

if __name__ == "__main__":
    test_2024_gemini_transactions() 