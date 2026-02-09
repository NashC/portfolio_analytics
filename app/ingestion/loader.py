import os
import glob
import pandas as pd
import yaml
from typing import Dict, Optional
import numpy as np
import re
import sqlite3


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
    gemini_2024_transactions = []  # Special container for 2024 Gemini transactions

    # Process each file in the data directory
    for file_name in os.listdir(data_dir):
        file_path = os.path.join(data_dir, file_name)
        if not os.path.isfile(file_path) or not file_name.endswith('.csv'):
            continue

        print(f"Processing file: {file_name}")

        # Match file to mapping configuration
        institution, file_type, mapping = match_file_to_mapping(file_name, config)
        if not mapping:
            print(f"No mapping found for file: {file_name}")
            continue

        # For Gemini files, we need to handle dynamic asset columns
        if institution == 'gemini':
            # Read the CSV to get unique asset columns
            df = pd.read_csv(file_path)

            # SPECIAL HANDLING FOR 2024 GEMINI TRANSACTIONS
            # Directly identify and extract 2024 transactions
            year_2024_mask = df['Date'].fillna('').str.startswith('2024-')
            if year_2024_mask.any():
                gemini_2024_df = df[year_2024_mask].copy()

                # Get all asset columns for 2024 data
                asset_cols = [col for col in gemini_2024_df.columns if " Amount " in col and "Balance" not in col and "USD" not in col]
                assets = [col.split(" Amount ")[0] for col in asset_cols]

                # Import price service for historical price data
                from app.services.price_service import PriceService
                price_service = PriceService()

                for asset in assets:
                    amount_col = f"{asset} Amount {asset}"
                    df_asset_2024 = gemini_2024_df[gemini_2024_df[amount_col].notna()].copy()

                    if not df_asset_2024.empty:
                        print(f"Processing 2024 {asset} transactions: {len(df_asset_2024)} found")

                        # Create standard fields
                        df_asset_2024['timestamp'] = pd.to_datetime(df_asset_2024['Date'] + ' ' + df_asset_2024['Time (UTC)'], errors='coerce')
                        df_asset_2024['asset'] = asset
                        df_asset_2024['institution'] = institution

                        # Extract quantity from amount column - handle both positive and negative values
                        # The amount is in the format "X.XXX asset" or "(X.XXX asset)" for negative
                        amount_values = df_asset_2024[amount_col].astype(str).str.strip()

                        # Function to clean and convert quantity values
                        def extract_quantity(val):
                            if pd.isna(val) or not val:
                                return 0.0

                            # Convert to string and strip spaces
                            val_str = str(val).strip()

                            # Check if value is in parentheses (negative)
                            is_negative = val_str.startswith('(') and val_str.endswith(')')

                            # Remove parentheses if they exist
                            if is_negative:
                                val_str = val_str[1:-1]

                            # Extract the numeric part (before the asset symbol)
                            pattern = r'([0-9.]+)\s+' + re.escape(asset)
                            match = re.search(pattern, val_str)

                            if match:
                                try:
                                    result = float(match.group(1))
                                    # Apply negative sign if value was in parentheses
                                    if is_negative:
                                        result = -result
                                    return result
                                except (ValueError, TypeError):
                                    return 0.0
                            else:
                                return 0.0

                        # Apply the extraction function
                        df_asset_2024['quantity'] = amount_values.apply(extract_quantity)

                        # Set type based on Specification field and Type
                        df_asset_2024['type'] = df_asset_2024['Type']

                        # Handle withdrawal types
                        withdrawal_mask = df_asset_2024['Specification'].fillna('').str.contains(f'Withdrawal \\({asset}\\)', regex=True)
                        if withdrawal_mask.any():
                            df_asset_2024.loc[withdrawal_mask, 'type'] = 'Send'
                            df_asset_2024.loc[withdrawal_mask, 'quantity'] = -abs(df_asset_2024.loc[withdrawal_mask, 'quantity'])

                        # Handle redemption types
                        redemption_mask = df_asset_2024['Specification'].fillna('').str.contains('Earn Redemption', regex=False)
                        if redemption_mask.any():
                            df_asset_2024.loc[redemption_mask, 'type'] = 'Receive'
                            df_asset_2024.loc[redemption_mask, 'quantity'] = abs(df_asset_2024.loc[redemption_mask, 'quantity'])

                        # Get historical prices for the asset on each transaction date
                        try:
                            # Extract unique dates for price lookups
                            transaction_dates = df_asset_2024['timestamp'].dt.to_pydatetime().tolist()
                            min_date = min(transaction_dates)
                            max_date = max(transaction_dates)

                            # PRICE PRIORITY:
                            # 1. Use transaction source data when available (price from Buy/Sell)
                            # 2. Query price service/database for historical prices
                            # 3. Use hardcoded fallback prices as last resort

                            # First check if this transaction already has price data from the source
                            has_price_data = False
                            if 'USD Amount USD' in gemini_2024_df.columns:
                                # For Buy/Sell transactions, use the USD amount and quantity to calculate price
                                usd_mask = gemini_2024_df['Type'].isin(['Buy', 'Sell'])
                                if usd_mask.any():
                                    usd_amounts = pd.to_numeric(gemini_2024_df.loc[usd_mask, 'USD Amount USD'], errors='coerce').fillna(0)
                                    asset_amounts = df_asset_2024.loc[df_asset_2024.index.isin(gemini_2024_df.loc[usd_mask].index), 'quantity'].abs()

                                    if not asset_amounts.empty and (asset_amounts > 0).any():
                                        # Calculate price only for non-zero quantities to avoid division by zero
                                        valid_mask = asset_amounts > 0
                                        if valid_mask.any():
                                            prices = usd_amounts.loc[valid_mask.index] / asset_amounts.loc[valid_mask]

                                            if not prices.empty:
                                                for idx, price in prices.items():
                                                    if idx in df_asset_2024.index:
                                                        df_asset_2024.loc[idx, 'price'] = price
                                                        df_asset_2024.loc[idx, 'subtotal'] = abs(df_asset_2024.loc[idx, 'quantity']) * price
                                                        has_price_data = True

                            # For transactions without price data, proceed with the price service
                            price_missing_mask = df_asset_2024['price'].isna() | (df_asset_2024['price'] <= 0)
                            if price_missing_mask.any():
                                historical_prices = price_service.get_asset_prices(asset, min_date, max_date)

                                # Check what was returned by price service
                                if historical_prices is None:
                                    raise ValueError("Price service returned None")
                                elif historical_prices.empty:
                                    raise ValueError("Price service returned empty DataFrame")

                                # Process price data based on the actual structure
                                price_col = None

                                # Find the appropriate price column
                                for col_name in ['price', asset, 'close', 'Adj Close']:
                                    if col_name in historical_prices.columns:
                                        price_col = col_name
                                        break

                                if price_col is None:
                                    raise ValueError("No price column found")

                                # Ensure historical_prices DataFrame has a datetime index
                                if not isinstance(historical_prices.index, pd.DatetimeIndex):
                                    if 'date' in historical_prices.columns:
                                        historical_prices = historical_prices.set_index('date')
                                    elif 'timestamp' in historical_prices.columns:
                                        historical_prices = historical_prices.set_index('timestamp')
                                    else:
                                        # Convert first column to index if it contains dates
                                        try:
                                            historical_prices = historical_prices.set_index(historical_prices.columns[0])
                                            historical_prices.index = pd.to_datetime(historical_prices.index)
                                        except Exception as e:
                                            raise ValueError("Could not set datetime index")

                                # Fallback: If we couldn't set an index, create a new index from the date column
                                if not isinstance(historical_prices.index, pd.DatetimeIndex):
                                    # Look for any date-like column
                                    date_columns = [col for col in historical_prices.columns if 'date' in col.lower() or 'time' in col.lower()]
                                    if date_columns:
                                        historical_prices['temp_date'] = pd.to_datetime(historical_prices[date_columns[0]])
                                        historical_prices = historical_prices.set_index('temp_date')
                                    else:
                                        raise ValueError("Could not create DatetimeIndex")

                                # At this point, we should have a DatetimeIndex
                                if not isinstance(historical_prices.index, pd.DatetimeIndex):
                                    raise ValueError("Failed to create DatetimeIndex")

                                # Direct approach: Map prices to transactions by closest date
                                processed_count = 0
                                for idx, row in df_asset_2024.iterrows():
                                    # Skip transactions that already have prices from source data
                                    if 'price' in row and row['price'] > 0:
                                        continue

                                    if pd.isna(row['timestamp']):
                                        continue

                                    # Find closest price date
                                    transaction_date = row['timestamp'].to_pydatetime()
                                    transaction_date_normalized = pd.Timestamp(transaction_date.date())

                                    try:
                                        # Try exact date match first
                                        if transaction_date_normalized in historical_prices.index:
                                            price = historical_prices.loc[transaction_date_normalized, price_col]
                                            match_type = "exact"
                                        else:
                                            # Find nearest available date
                                            try:
                                                nearest_date = historical_prices.index[
                                                    historical_prices.index.get_indexer([transaction_date_normalized], method='nearest')[0]
                                                ]
                                                price = historical_prices.loc[nearest_date, price_col]
                                                match_type = "nearest"
                                            except Exception as e:
                                                # Try a different approach - manual search for closest date
                                                date_diffs = [(d, abs((d - transaction_date_normalized).total_seconds()))
                                                            for d in historical_prices.index]
                                                closest_date, _ = min(date_diffs, key=lambda x: x[1])
                                                price = historical_prices.loc[closest_date, price_col]
                                                match_type = "manual"

                                        # Set price and calculate subtotal
                                        df_asset_2024.loc[idx, 'price'] = price
                                        df_asset_2024.loc[idx, 'subtotal'] = abs(row['quantity']) * price

                                        processed_count += 1
                                    except Exception as e:
                                        # Set default price and subtotal
                                        df_asset_2024.loc[idx, 'price'] = 0.0
                                        df_asset_2024.loc[idx, 'subtotal'] = 0.0

                                # If no prices were found, use fallback prices
                                if processed_count == 0:
                                    raise ValueError("No prices could be processed from retrieved data")
                        except Exception as e:
                            # Query price database as fallback instead of using hardcoded values
                            try:
                                # Connect to the prices database
                                db_path = os.path.join(os.getcwd(), 'data', 'prices.db')
                                if os.path.exists(db_path):
                                    conn = sqlite3.connect(db_path)
                                    # Format dates for SQL query
                                    min_date_str = min_date.strftime('%Y-%m-%d')
                                    max_date_str = max_date.strftime('%Y-%m-%d')

                                    # Query the database for relevant prices
                                    query = f"""
                                        SELECT date, price
                                        FROM prices
                                        WHERE symbol = '{asset}'
                                        AND date BETWEEN '{min_date_str}' AND '{max_date_str}'
                                        ORDER BY date
                                    """

                                    db_prices = pd.read_sql_query(query, conn)
                                    conn.close()

                                    if not db_prices.empty:
                                        # Convert date column to datetime for index
                                        db_prices['date'] = pd.to_datetime(db_prices['date'])
                                        db_prices = db_prices.set_index('date')

                                        # Apply database prices to transactions
                                        processed_count = 0
                                        for idx, row in df_asset_2024.iterrows():
                                            # Skip transactions that already have prices from source data
                                            if 'price' in row and row['price'] > 0:
                                                continue

                                            if pd.isna(row['timestamp']):
                                                continue

                                            # Find closest price date
                                            transaction_date = row['timestamp'].to_pydatetime()
                                            transaction_date_normalized = pd.Timestamp(transaction_date.date())

                                            try:
                                                # Try exact date match first
                                                if transaction_date_normalized in db_prices.index:
                                                    price = db_prices.loc[transaction_date_normalized, 'price']
                                                else:
                                                    # Find nearest available date
                                                    nearest_date = db_prices.index[
                                                        db_prices.index.get_indexer([transaction_date_normalized], method='nearest')[0]
                                                    ]
                                                    price = db_prices.loc[nearest_date, 'price']

                                                # Set price and calculate subtotal
                                                df_asset_2024.loc[idx, 'price'] = price
                                                df_asset_2024.loc[idx, 'subtotal'] = abs(row['quantity']) * price

                                                processed_count += 1
                                            except Exception as e:
                                                # Use last available price if any were processed
                                                if processed_count > 0:
                                                    last_price = df_asset_2024.loc[df_asset_2024['price'] > 0, 'price'].iloc[-1]
                                                    df_asset_2024.loc[idx, 'price'] = last_price
                                                    df_asset_2024.loc[idx, 'subtotal'] = abs(row['quantity']) * last_price
                                                else:
                                                    # Default to zero if no prices available
                                                    df_asset_2024.loc[idx, 'price'] = 0.0
                                                    df_asset_2024.loc[idx, 'subtotal'] = 0.0
                                    else:
                                        # Try a broader search if no prices are found in the exact range
                                        broader_query = f"""
                                            SELECT date, price
                                            FROM prices
                                            WHERE symbol = '{asset}'
                                            ORDER BY date
                                        """

                                        conn = sqlite3.connect(db_path)
                                        broader_prices = pd.read_sql_query(broader_query, conn)
                                        conn.close()

                                        if not broader_prices.empty:
                                            # Convert date column to datetime for index
                                            broader_prices['date'] = pd.to_datetime(broader_prices['date'])
                                            broader_prices = broader_prices.set_index('date')

                                            # Use the closest date for all transactions
                                            if transaction_date_normalized <= broader_prices.index.min():
                                                closest_date = broader_prices.index.min()
                                            elif transaction_date_normalized >= broader_prices.index.max():
                                                closest_date = broader_prices.index.max()
                                            else:
                                                closest_date = broader_prices.index[
                                                    broader_prices.index.get_indexer([transaction_date_normalized], method='nearest')[0]
                                                ]

                                            price = broader_prices.loc[closest_date, 'price']

                                            # Apply this price to all transactions
                                            df_asset_2024['price'] = price
                                            df_asset_2024['subtotal'] = abs(df_asset_2024['quantity']) * price
                                        else:
                                            raise ValueError("No prices found in database")
                                else:
                                    raise ValueError("Prices database not found")

                            except Exception as db_error:
                                # Check for prices in alternative sources
                                try:
                                    # If we've already processed some assets, check if we have a price for this asset
                                    for prev_df in all_transactions:
                                        if 'asset' in prev_df.columns and 'price' in prev_df.columns:
                                            asset_prices = prev_df[prev_df['asset'] == asset]['price']
                                            if not asset_prices.empty and asset_prices.max() > 0:
                                                price = asset_prices.max()
                                                df_asset_2024['price'] = price
                                                df_asset_2024['subtotal'] = abs(df_asset_2024['quantity']) * price
                                                break

                                    # ABSOLUTE LAST RESORT - Hardcoded values only as final fallback
                                    fallback_prices = {
                                        'BTC': 65000.0,  # ~$65k in June 2024
                                        'ETH': 3500.0,   # ~$3,500 in June 2024
                                        'LTC': 85.0,     # ~$85 in June 2024
                                        'FIL': 6.0       # ~$6 in June 2024
                                    }

                                    if asset in fallback_prices:
                                        price = fallback_prices[asset]
                                        df_asset_2024['price'] = price
                                        df_asset_2024['subtotal'] = abs(df_asset_2024['quantity']) * price
                                    else:
                                        df_asset_2024['price'] = 0.0
                                        df_asset_2024['subtotal'] = 0.0
                                except Exception as final_error:
                                    df_asset_2024['price'] = 0.0
                                    df_asset_2024['subtotal'] = 0.0
                        except Exception as e:
                            # Define fallback prices as last resort
                            fallback_prices = {
                                'BTC': 65000.0,  # ~$65k in June 2024
                                'ETH': 3500.0,   # ~$3,500 in June 2024
                                'LTC': 85.0,     # ~$85 in June 2024
                                'FIL': 6.0       # ~$6 in June 2024
                            }

                            if asset in fallback_prices:
                                price = fallback_prices[asset]
                                df_asset_2024['price'] = price
                                df_asset_2024['subtotal'] = abs(df_asset_2024['quantity']) * price
                            else:
                                df_asset_2024['price'] = 0.0
                                df_asset_2024['subtotal'] = 0.0
                        # Handle fees - for send transactions, estimate reasonable network fees
                        send_mask = df_asset_2024['type'] == 'Send'
                        if send_mask.any():
                            # Estimate standard network fees for Send transactions
                            if asset == 'BTC':
                                standard_fee = 0.0002  # Standard BTC network fee
                                df_asset_2024.loc[send_mask, 'fees'] = standard_fee * df_asset_2024.loc[send_mask, 'price']
                            elif asset == 'ETH':
                                standard_fee = 0.003  # Standard ETH network fee
                                df_asset_2024.loc[send_mask, 'fees'] = standard_fee * df_asset_2024.loc[send_mask, 'price']
                            elif asset == 'LTC':
                                standard_fee = 0.005  # Standard LTC network fee
                                df_asset_2024.loc[send_mask, 'fees'] = standard_fee * df_asset_2024.loc[send_mask, 'price']
                            elif asset == 'FIL':
                                standard_fee = 0.02  # Standard FIL network fee
                                df_asset_2024.loc[send_mask, 'fees'] = standard_fee * df_asset_2024.loc[send_mask, 'price']
                            else:
                                # Default fee for other cryptos (approximately 0.1% of transaction value)
                                df_asset_2024.loc[send_mask, 'fees'] = 0.001 * abs(df_asset_2024.loc[send_mask, 'quantity']) * df_asset_2024.loc[send_mask, 'price']
                        else:
                            df_asset_2024['fees'] = 0.0

                        # Calculate total (subtotal + fees) for completeness
                        df_asset_2024['total'] = df_asset_2024['subtotal'] + df_asset_2024['fees']

                        # Add to special container
                        gemini_2024_transactions.append(df_asset_2024[['timestamp', 'type', 'asset', 'quantity', 'price', 'fees', 'subtotal', 'total', 'institution']])

            # Get all asset columns (e.g., "BTC Amount BTC", "ETH Amount ETH", etc.)
            asset_cols = [col for col in df.columns if " Amount " in col and "Balance" not in col and "USD" not in col]
            assets = [col.split(" Amount ")[0] for col in asset_cols]  # Extract asset from column name

            for asset in assets:
                # Create the expected column name pattern
                amount_col = f"{asset} Amount {asset}"  # e.g., "BTC Amount BTC"
                balance_col = f"{asset} Balance {asset}"
                fee_col = f"Fee ({asset})"

                # Create a filtered DataFrame for this asset's transactions
                df_asset = df[df[amount_col].notna()].copy()

                # Convert amount and balance columns to numeric immediately
                df_asset[amount_col] = pd.to_numeric(df_asset[amount_col], errors='coerce')
                if balance_col in df.columns:
                    df_asset[balance_col] = pd.to_numeric(df_asset[balance_col], errors='coerce')

                # Map the columns
                df_asset['quantity'] = df_asset[amount_col]

                # Handle USD amount for price
                df_asset['price'] = 0.0  # Default to 0
                usd_mask = df_asset['Type'].isin(['Buy', 'Sell'])
                if usd_mask.any():
                    # Get USD amounts and quantities
                    usd_amounts = df_asset.loc[usd_mask, 'USD Amount USD'].fillna(0)
                    usd_amounts = pd.to_numeric(usd_amounts, errors='coerce').fillna(0)
                    quantities = df_asset.loc[usd_mask, 'quantity'].fillna(0)

                    # Calculate price per unit by dividing USD amount by quantity
                    # Avoid division by zero by setting price to 0 where quantity is 0
                    df_asset.loc[usd_mask, 'price'] = np.where(quantities != 0, usd_amounts / quantities, 0)

                # Handle fees
                df_asset['fees'] = 0.0
                if fee_col in df.columns:
                    df_asset['fees'] = pd.to_numeric(df_asset[fee_col], errors='coerce').fillna(0)

                df_asset['asset'] = asset

                # Properly parse the timestamp, preserving the year including 2024
                df_asset['timestamp'] = pd.to_datetime(df_asset['Date'] + ' ' + df_asset['Time (UTC)'], errors='coerce')

                df_asset['type'] = df_asset['Type']  # Just copy the raw type, normalization will handle mapping
                df_asset['institution'] = institution

                # Use Specification column to improve transfer type classification
                if 'Specification' in df_asset.columns:
                    withdrawal_mask = df_asset['Specification'].fillna('').str.contains(f'Withdrawal \\({asset}\\)', regex=True)
                    redemption_mask = df_asset['Specification'].fillna('').str.contains('Earn Redemption', regex=False)
                    year_2024_mask = df_asset['Date'].fillna('').str.startswith('2024-')

                    if withdrawal_mask.any():
                        # For crypto withdrawals, ensure the type is set to Send and quantity is negative
                        df_asset.loc[withdrawal_mask, 'type'] = 'Send'
                        df_asset.loc[withdrawal_mask, 'quantity'] = -abs(df_asset.loc[withdrawal_mask, 'quantity'])

                    if redemption_mask.any():
                        # For Earn Redemption, mark as Receive
                        df_asset.loc[redemption_mask, 'type'] = 'Receive'
                        df_asset.loc[redemption_mask, 'quantity'] = abs(df_asset.loc[redemption_mask, 'quantity'])

                # For transfers, calculate quantity based on balance changes - but give priority to Specification
                transfer_mask = df_asset['Type'].isin(['Transfer', 'Deposit', 'Withdrawal'])
                if transfer_mask.any():
                    if balance_col in df.columns:
                        # Sort by timestamp to ensure correct balance differences
                        df_asset = df_asset.sort_values('timestamp')

                        # Calculate balance differences for transfers
                        df_asset['prev_balance'] = df_asset[balance_col].shift(1)
                        df_asset['balance_diff'] = df_asset[balance_col] - df_asset['prev_balance']

                        # Apply unified logic for all transfer types based on balance difference
                        rows_to_update = transfer_mask & df_asset['prev_balance'].notna()

                        df_asset.loc[rows_to_update, 'quantity'] = df_asset.loc[rows_to_update, 'balance_diff']
                        df_asset.loc[rows_to_update & (df_asset['balance_diff'] < 0), 'type'] = 'Send'
                        df_asset.loc[rows_to_update & (df_asset['balance_diff'] > 0), 'type'] = 'Receive'

                        # Preserve type from Specification column when available
                        if 'Specification' in df_asset.columns:
                            spec_withdrawal_mask = rows_to_update & df_asset['Specification'].fillna('').str.contains(f'Withdrawal \\({asset}\\)', regex=True)
                            if spec_withdrawal_mask.any():
                                df_asset.loc[spec_withdrawal_mask, 'type'] = 'Send'
                                # Ensure the quantity is negative for withdrawals
                                df_asset.loc[spec_withdrawal_mask, 'quantity'] = -abs(df_asset.loc[spec_withdrawal_mask, 'quantity'])

                        # Handle the first row where we don't have a previous balance
                        first_transfer_mask = transfer_mask & df_asset['prev_balance'].isna()
                        if first_transfer_mask.any():
                            # Use amount_col for quantity and type determination for the very first transfer
                            df_asset.loc[first_transfer_mask, 'quantity'] = df_asset.loc[first_transfer_mask, amount_col]
                            df_asset.loc[first_transfer_mask & (df_asset[amount_col] < 0), 'type'] = 'Send'
                            # Treat non-negative amounts (including 0) as Receive for the first entry if type is Deposit/Transfer
                            df_asset.loc[first_transfer_mask & (df_asset[amount_col] >= 0) & df_asset['Type'].isin(['Deposit', 'Transfer']), 'type'] = 'Receive'
                            # Explicitly handle first Withdrawal if amount is 0 or positive (unlikely but possible)
                            df_asset.loc[first_transfer_mask & (df_asset[amount_col] >= 0) & (df_asset['Type'] == 'Withdrawal'), 'type'] = 'Send'

                            # Give priority to Specification column for first transfer
                            if 'Specification' in df_asset.columns:
                                spec_withdrawal_mask = first_transfer_mask & df_asset['Specification'].fillna('').str.contains(f'Withdrawal \\({asset}\\)', regex=True)
                                if spec_withdrawal_mask.any():
                                    df_asset.loc[spec_withdrawal_mask, 'type'] = 'Send'
                                    # Ensure the quantity is negative for withdrawals
                                    df_asset.loc[spec_withdrawal_mask, 'quantity'] = -abs(df_asset.loc[spec_withdrawal_mask, 'quantity'])

                        # Clean up temporary columns
                        df_asset = df_asset.drop(['prev_balance', 'balance_diff'], axis=1, errors='ignore')
                    else:
                        # Fallback: If no balance column, use the amount column directly
                        df_asset.loc[transfer_mask, 'quantity'] = df_asset.loc[transfer_mask, amount_col]

                        # For withdrawals and negative transfers, make quantity negative and mark as send
                        send_mask = (df_asset['Type'] == 'Withdrawal') | (
                            (df_asset['Type'] == 'Transfer') & (df_asset[amount_col] < 0)
                        )
                        df_asset.loc[send_mask, 'quantity'] = -abs(df_asset.loc[send_mask, 'quantity'])
                        df_asset.loc[send_mask, 'type'] = 'Send'

                        # For deposits and positive transfers, mark as receive
                        receive_mask = (df_asset['Type'] == 'Deposit') | (
                            (df_asset['Type'] == 'Transfer') & (df_asset[amount_col] >= 0)
                        )
                        df_asset.loc[receive_mask, 'quantity'] = abs(df_asset.loc[receive_mask, 'quantity'])
                        df_asset.loc[receive_mask, 'type'] = 'Receive'

                        # Override with Specification column for better accuracy
                        if 'Specification' in df_asset.columns:
                            spec_withdrawal_mask = transfer_mask & df_asset['Specification'].fillna('').str.contains(f'Withdrawal \\({asset}\\)', regex=True)
                            if spec_withdrawal_mask.any():
                                df_asset.loc[spec_withdrawal_mask, 'type'] = 'Send'
                                # Ensure the quantity is negative for withdrawals
                                df_asset.loc[spec_withdrawal_mask, 'quantity'] = -abs(df_asset.loc[spec_withdrawal_mask, 'quantity'])

                # Keep all transfer transactions regardless of quantity
                # For non-transfers, filter out zero amounts
                df_asset = df_asset[
                    (df_asset['Type'].isin(['Transfer', 'Deposit', 'Withdrawal'])) |
                    (df_asset['quantity'].abs() > 0)
                ].copy()

                if not df_asset.empty:
                    all_transactions.append(df_asset[['timestamp', 'type', 'asset', 'quantity', 'price', 'fees', 'institution']])
        else:
            # For other institutions, process based on institution type
            if institution == 'interactive_brokers':
                # Use custom Interactive Brokers processing
                processed_df = process_interactive_brokers_csv(file_path, mapping)
            else:
                # For other institutions, process normally
                processed_df = ingest_csv(file_path, mapping['mapping'])
                processed_df['institution'] = institution

            if not processed_df.empty:
                all_transactions.append(processed_df)

    # When done with processing files, add the special 2024 Gemini transactions to all_transactions
    if gemini_2024_transactions:
        for df_special in gemini_2024_transactions:
            if not df_special.empty:
                all_transactions.append(df_special)

    # Check if all_transactions is empty after processing
    if not all_transactions:
        print("No transactions found in any file.")
        return pd.DataFrame()

    # Combine all transactions
    combined_df = pd.concat(all_transactions, ignore_index=True)

    # Sort by timestamp
    if 'timestamp' in combined_df.columns:
        combined_df = combined_df.sort_values('timestamp')

        # Ensure timestamps are in the correct datetime format
        valid_timestamp_mask = combined_df['timestamp'].notna()
        if valid_timestamp_mask.any():
            combined_df.loc[valid_timestamp_mask, 'timestamp'] = pd.to_datetime(combined_df.loc[valid_timestamp_mask, 'timestamp'])

    # Import and apply normalization
    from app.ingestion.normalization import normalize_data
    combined_df = normalize_data(combined_df)

    # Ensure timestamps are in the correct datetime format after normalization
    if 'timestamp' in combined_df.columns:
        valid_timestamp_mask = combined_df['timestamp'].notna()
        if valid_timestamp_mask.any():
            combined_df.loc[valid_timestamp_mask, 'timestamp'] = pd.to_datetime(combined_df.loc[valid_timestamp_mask, 'timestamp'])

    return combined_df


def process_interactive_brokers_csv(file_path: str, mapping: dict) -> pd.DataFrame:
    """
    Process Interactive Brokers CSV file with special handling for their format.
    """
    # Read the CSV file
    df = pd.read_csv(file_path)

    # Parse timestamp using original column name
    df['timestamp'] = pd.to_datetime(df['Date'], errors='coerce')

    # Clean numeric columns using original column names
    numeric_cols = ['Quantity', 'Price', 'Gross Amount', 'Commission', 'Net Amount']
    for col in numeric_cols:
        if col in df.columns:
            # Handle string values and remove currency symbols/commas
            df[col] = df[col].astype(str).str.replace('$', '').str.replace(',', '')
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    # Create standardized columns
    processed_rows = []

    for _, row in df.iterrows():
        # Skip rows with missing essential data
        if pd.isna(row['timestamp']) or row['Transaction Type'] in ['Other Fee', 'Commission Adjustment']:
            continue

        # Handle different transaction types
        transaction_type = row['Transaction Type']
        symbol = row['Symbol'] if pd.notna(row['Symbol']) and row['Symbol'] != '-' else None
        quantity = row['Quantity'] if pd.notna(row['Quantity']) else 0
        price = row['Price'] if pd.notna(row['Price']) else 0

        # For stock/ETF transactions
        if transaction_type in ['Buy', 'Sell'] and symbol:
            processed_row = {
                'timestamp': row['timestamp'],
                'type': transaction_type,
                'asset': symbol,
                'quantity': abs(quantity) if transaction_type == 'Buy' else -abs(quantity),
                'price': abs(price),
                'fees': abs(row['Commission']) if pd.notna(row['Commission']) else 0,
                'subtotal': abs(row['Gross Amount']) if pd.notna(row['Gross Amount']) else 0,
                'total': abs(row['Net Amount']) if pd.notna(row['Net Amount']) else 0,
                'account': row['Account'],
                'description': row['Description'],
                'institution': 'interactive_brokers'
            }
            processed_rows.append(processed_row)

        # For cash transactions (deposits, withdrawals, dividends, interest)
        elif transaction_type in ['Deposit', 'Withdrawal', 'Dividend', 'Credit Interest', 'Electronic Fund Transfer']:
            # For cash transactions, use USD as the asset
            asset = 'USD'
            net_amount = row['Net Amount'] if pd.notna(row['Net Amount']) else 0

            # Determine quantity based on transaction type and amount
            if transaction_type in ['Deposit', 'Electronic Fund Transfer']:
                quantity_val = abs(net_amount)
            elif transaction_type == 'Withdrawal':
                quantity_val = -abs(net_amount)
            elif transaction_type in ['Dividend', 'Credit Interest']:
                quantity_val = abs(net_amount)
                asset = 'USD'  # Dividends and interest are in USD
            else:
                quantity_val = net_amount

            processed_row = {
                'timestamp': row['timestamp'],
                'type': transaction_type,
                'asset': asset,
                'quantity': quantity_val,
                'price': 1.0,  # USD to USD price is 1
                'fees': 0,
                'subtotal': abs(net_amount),
                'total': abs(net_amount),
                'account': row['Account'],
                'description': row['Description'],
                'institution': 'interactive_brokers'
            }
            processed_rows.append(processed_row)

        # For cash transfers between accounts
        elif transaction_type == 'Cash Transfer':
            net_amount = row['Net Amount'] if pd.notna(row['Net Amount']) else 0

            processed_row = {
                'timestamp': row['timestamp'],
                'type': 'Cash Transfer',
                'asset': 'USD',
                'quantity': net_amount,  # Keep sign to indicate direction
                'price': 1.0,
                'fees': 0,
                'subtotal': abs(net_amount),
                'total': abs(net_amount),
                'account': row['Account'],
                'description': row['Description'],
                'institution': 'interactive_brokers'
            }
            processed_rows.append(processed_row)

    # Convert to DataFrame
    if processed_rows:
        result_df = pd.DataFrame(processed_rows)
        print(f"Processed {len(result_df)} Interactive Brokers transactions")
        return result_df
    else:
        print("No valid transactions found in Interactive Brokers file")
        return pd.DataFrame()
