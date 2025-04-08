import os
import glob
import pandas as pd
import yaml
from typing import Dict, Optional
import numpy as np


def load_schema_config(config_path: str) -> Dict:
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


def parse_timestamp(row: pd.Series, date_col: str, time_col: Optional[str] = None) -> pd.Timestamp:
    if time_col and time_col in row and pd.notna(row[time_col]):
        return pd.to_datetime(f"{row[date_col]} {row[time_col]}")
    return pd.to_datetime(row[date_col])


def ingest_csv(file_path: str, mapping: dict, file_type: str = None) -> pd.DataFrame:
    """
    Load and process a CSV file according to the provided mapping.
    """
    df = pd.read_csv(file_path)
    
    # Create a reverse mapping to rename columns
    reverse_mapping = {v: k for k, v in mapping.items() if v}
    df = df.rename(columns=reverse_mapping)
    
    # Parse timestamp and convert to UTC
    if 'timestamp' in df.columns:
        df['timestamp'] = pd.to_datetime(df['timestamp']).dt.tz_localize(None)
    elif 'Date' in df.columns and 'Time (UTC)' in df.columns:
        df['timestamp'] = pd.to_datetime(df['Date'] + ' ' + df['Time (UTC)']).dt.tz_localize(None)
    
    # Clean numeric columns
    numeric_cols = ['quantity', 'price', 'subtotal', 'total', 'fees']
    for col in numeric_cols:
        if col in df.columns:
            # Convert to string first to handle any formatting
            df[col] = df[col].astype(str)
            # Remove currency symbols and commas
            df[col] = df[col].str.replace('$', '').str.replace(',', '')
            # Convert to numeric
            df[col] = pd.to_numeric(df[col], errors='coerce')
            
            # For fees, ensure they are positive
            if col == 'fees':
                df[col] = df[col].abs()
    
    # Inject constant fields from mapping if present
    if 'constants' in mapping:
        for field, value in mapping['constants'].items():
            df[field] = value
            
    return df


def match_file_to_mapping(file_name: str, schema_config: dict):
    """
    Matches a given file name against the schema configuration.
    
    Returns a tuple (institution, subtype, mapping) if found, otherwise (None, None, None).
    """
    for institution, entry in schema_config.items():
        # Check for direct mapping with a file_pattern
        if isinstance(entry, dict) and "file_pattern" in entry:
            if file_name == entry["file_pattern"]:
                return institution, None, entry
        # Check for nested mappings (e.g., gemini with staking and transactions)
        elif isinstance(entry, dict):
            for sub_key, sub_entry in entry.items():
                if isinstance(sub_entry, dict) and "file_pattern" in sub_entry:
                    if file_name == sub_entry["file_pattern"]:
                        return institution, sub_key, sub_entry
    return None, None, None


def process_transactions(data_dir: str, config_path: str) -> pd.DataFrame:
    """
    Process all transaction files in the data directory according to schema mappings.
    """
    config = load_schema_config(config_path)
    all_transactions = []
    
    # Process each file in the data directory
    for file_name in os.listdir(data_dir):
        file_path = os.path.join(data_dir, file_name)
        if not os.path.isfile(file_path) or not file_name.endswith('.csv'):
            continue
            
        # Match file to mapping configuration
        institution, file_type, mapping = match_file_to_mapping(file_name, config)
        if not mapping:
            print(f"No mapping found for file: {file_name}")
            continue
            
        # For Gemini files, we need to handle dynamic asset columns
        if institution == 'gemini':
            # Read the CSV to get unique asset columns
            df = pd.read_csv(file_path)
            
            # Get all asset columns (e.g., "BTC Amount BTC", "ETH Amount ETH", etc.)
            asset_cols = [col for col in df.columns if "Amount" in col and "Balance" not in col and "USD" not in col]
            assets = [col.split()[0] for col in asset_cols]
            
            for asset, amount_col in zip(assets, asset_cols):
                # Create a filtered DataFrame for this asset's transactions
                df_asset = df[df[amount_col].notna() & (df[amount_col] != f"0.0 {asset}")].copy()
                if df_asset.empty:
                    continue
                
                # Map the columns
                df_asset['quantity'] = df_asset[amount_col].str.replace(asset, '').str.strip(' ()')
                
                # Handle USD amount for price
                df_asset['price'] = 0.0  # Default to 0
                usd_mask = df_asset['Type'].isin(['Buy', 'Sell'])
                if usd_mask.any():
                    # Get USD amounts and quantities
                    usd_amounts = df_asset.loc[usd_mask, 'USD Amount USD'].fillna('$0.00')
                    usd_amounts = pd.to_numeric(usd_amounts.str.replace('$', '').str.replace(',', '').str.strip(' ()'), errors='coerce').fillna(0)
                    quantities = pd.to_numeric(df_asset.loc[usd_mask, 'quantity'], errors='coerce').fillna(0)
                    
                    # Calculate price per unit by dividing USD amount by quantity
                    # Avoid division by zero by setting price to 0 where quantity is 0
                    df_asset.loc[usd_mask, 'price'] = np.where(quantities != 0, usd_amounts / quantities, 0)
                
                # Handle fees
                df_asset['fees'] = 0.0
                if f'Fee ({asset}) {asset}' in df.columns:
                    asset_fees = df_asset[f'Fee ({asset}) {asset}'].fillna('0.0').str.replace(asset, '').str.strip(' ()')
                    df_asset['fees'] = pd.to_numeric(asset_fees, errors='coerce').fillna(0)
                
                df_asset['asset'] = asset
                df_asset['timestamp'] = pd.to_datetime(df_asset['Date'] + ' ' + df_asset['Time (UTC)'])
                df_asset['type'] = df_asset['Type']  # Just copy the raw type, normalization will handle mapping
                
                # Convert numeric columns
                numeric_cols = ['quantity']
                for col in numeric_cols:
                    df_asset[col] = pd.to_numeric(df_asset[col], errors='coerce').fillna(0)
                
                df_asset['institution'] = institution
                
                all_transactions.append(df_asset[['timestamp', 'type', 'asset', 'quantity', 'price', 'fees', 'institution']])
        else:
            # For other institutions, process normally
            processed_df = ingest_csv(file_path, mapping['mapping'])
            processed_df['institution'] = institution
            all_transactions.append(processed_df)
    
    if not all_transactions:
        return pd.DataFrame()
    
    # Combine all transactions
    combined_df = pd.concat(all_transactions, ignore_index=True)
    
    # Sort by timestamp
    if 'timestamp' in combined_df.columns:
        combined_df = combined_df.sort_values('timestamp')
    
    # Import and apply normalization
    from normalization import normalize_data
    combined_df = normalize_data(combined_df)
    
    return combined_df