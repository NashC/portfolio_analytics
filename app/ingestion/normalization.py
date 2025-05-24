import pandas as pd
from app.commons.utils import clean_numeric_column

# Expanded mapping for raw transaction types to our canonical set.
TRANSACTION_TYPE_MAP = {
    # Binance US
    'DEPOSIT': 'deposit',
    'WITHDRAWAL': 'withdrawal',
    'BUY': 'buy',
    'SELL': 'sell',
    'DISTRIBUTION': 'staking_reward',
    'COMMISSION_REBATE': 'rebate',
    'TRANSFER': 'transfer',
    'STAKING': 'staking_reward',
    'UNSTAKING': 'unstaking',
    'COMMISSION': 'fee',
    
    # Coinbase
    'Receive': 'transfer_in',
    'Send': 'transfer_out',
    'Buy': 'buy',
    'Sell': 'sell',
    'Rewards Income': 'staking_reward',
    'Coinbase Earn': 'reward',
    'Learning Reward': 'reward',
    'Staking Income': 'staking_reward',
    'Advanced Trade Buy': 'buy',
    'Advanced Trade Sell': 'sell',
    'Convert': 'trade',
    
    # Gemini
    'Credit': 'transfer_in',
    'Debit': 'transfer_out',
    'Buy': 'buy',
    'Sell': 'sell',
    'Reward': 'staking_reward',
    'Transfer': 'transfer',
    'Send': 'transfer_out',
    'Receive': 'transfer_in',
    'Earn': 'staking_reward',
    'Custody Transfer': 'transfer',
    'Admin Credit': 'transfer_in',
    'Admin Debit': 'transfer_out',
    'Deposit': 'deposit',
    'Withdrawal': 'withdrawal',
    'Trade': 'trade',
    'Reward Payout': 'staking_reward',
    'Earn Payout': 'staking_reward',
    'Earn Interest': 'staking_reward',
    'Earn Redemption': 'unstaking',
    'Earn Deposit': 'staking',
    'Earn Withdrawal': 'unstaking',
    'Deposit Credit': 'deposit',
    'Withdrawal Debit': 'withdrawal',
    'Exchange Buy': 'buy',
    'Exchange Sell': 'sell',
    'Exchange Trade': 'trade',
    'Deposit Initiated': 'deposit',
    'Withdrawal Initiated': 'withdrawal',
    'Deposit Confirmed': 'deposit',
    'Withdrawal Confirmed': 'withdrawal',
    'Deposit Reversed': 'withdrawal',
    'Withdrawal Reversed': 'deposit',

    # DEPOSIT / WITHDRAWAL
    "deposit": "deposit",
    "Deposit": "deposit",
    "exchange deposit": "deposit",
    "Exchange Deposit": "deposit",
    "withdraw": "withdrawal",
    "Withdraw": "withdrawal",
    "withdrawal": "withdrawal",
    "Withdrawal": "withdrawal",
    "exchange withdrawal": "withdrawal",
    "Exchange Withdrawal": "withdrawal",
    "Crypto Deposit": "transfer_in",  # Binance specific
    "Crypto Withdrawal": "transfer_out",  # Binance specific

    # TRANSFERS
    "receive": "transfer_in",
    "Receive": "transfer_in",
    "credit": "transfer_in",
    "Credit": "transfer_in",
    "send": "transfer_out",
    "Send": "transfer_out",
    "debit": "transfer_out",
    "Debit": "transfer_out",
    "administrative debit": "transfer_out",
    "Administrative Debit": "transfer_out",
    "distribution": "transfer_in",
    "Distribution": "transfer_in",
    "Transfer": "transfer_out",  # Coinbase specific
    "Transfer from Coinbase": "transfer_in",  # Coinbase specific
    "Transfer to Coinbase": "transfer_out",  # Coinbase specific
    "Coinbase Pro Transfer": "transfer_out",  # Coinbase specific
    "Coinbase Pro Transfer In": "transfer_in",  # Coinbase specific
    "Coinbase Pro Transfer Out": "transfer_out",  # Coinbase specific

    # STAKING / REWARDS
    "staking income": "staking_reward",
    "Staking Income": "staking_reward",
    "reward income": "staking_reward",
    "Reward Income": "staking_reward",
    "interest credit": "staking_reward",
    "Interest Credit": "staking_reward",
    "inflation reward": "staking_reward",
    "Inflation Reward": "staking_reward",

    # CONVERSIONS / SWAPS
    "convert": "swap",
    "Convert": "swap",
    "conversion": "swap",
    "Conversion": "swap",
    "redeem": "swap",
    "Redeem": "swap",

    # NON-TRANSACTIONAL (to be skipped or tagged)
    "monthly interest summary": "non_transactional",
    "Monthly Interest Summary": "non_transactional",

    # Fallback for empty strings, etc.
    "": "unknown",
}

def normalize_transaction_types(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalize the 'type' column to a canonical set using TRANSACTION_TYPE_MAP.
    Any unmapped types are flagged as 'unknown'.
    """
    print("\n=== Starting Transaction Type Normalization ===")
    print(f"Total transactions to process: {len(df)}")
    
    # Debug print raw transaction types
    print("\nRaw transaction types before normalization:")
    raw_types = df["type"].fillna("").astype(str).str.strip()
    print(raw_types.value_counts())
    
    # Initialize mapped types as unknown
    mapped = pd.Series("unknown", index=df.index)
    
    # Handle Binance specific cases first
    if any(col.lower() == "operation" for col in df.columns):
        operation_col = next(col for col in df.columns if col.lower() == "operation")
        print("\nBinance operations found:")
        operations = df[operation_col].fillna("").astype(str).str.strip()
        print(operations.value_counts())
        
        # Create a mask for crypto transfers
        crypto_deposit_mask = (operations.str.lower() == "crypto deposit")
        crypto_withdrawal_mask = (operations.str.lower() == "crypto withdrawal")
        
        # Map crypto transfers
        mapped[crypto_deposit_mask] = "transfer_in"
        mapped[crypto_withdrawal_mask] = "transfer_out"
        
        print("\nAfter Binance transfer mapping:")
        print(mapped.value_counts())
    
    # Handle Coinbase specific cases
    if "Transaction Type" in df.columns:
        print("\nCoinbase transaction types found:")
        coinbase_types = df["Transaction Type"].fillna("").astype(str).str.strip()
        print(coinbase_types.value_counts())
        
        # For Coinbase, check for transfer-related transaction types
        transfer_in_mask = coinbase_types.str.lower().isin([
            "transfer from coinbase",
            "coinbase pro transfer in"
        ])
        transfer_out_mask = coinbase_types.str.lower().isin([
            "transfer",
            "transfer to coinbase",
            "coinbase pro transfer",
            "coinbase pro transfer out"
        ])
        
        # Map Coinbase transfers
        mapped[transfer_in_mask] = "transfer_in"
        mapped[transfer_out_mask] = "transfer_out"
        
        print("\nAfter Coinbase transfer mapping:")
        print(mapped.value_counts())
    
    # Create case-insensitive mapping by converting all keys to lowercase
    case_insensitive_map = {k.lower(): v for k, v in TRANSACTION_TYPE_MAP.items()}
    
    # Map remaining transaction types (excluding transfers)
    remaining_mask = mapped == "unknown"
    if remaining_mask.any():
        # For remaining transactions, try to map from the type column
        raw_types_lower = raw_types[remaining_mask].str.lower()
        mapped[remaining_mask] = raw_types_lower.map(case_insensitive_map).fillna("unknown")
        
        print("\nAfter general mapping:")
        print(mapped.value_counts())
        
        # For any remaining unknowns, try to infer from other columns
        still_unknown = mapped == "unknown"
        if still_unknown.any():
            print("\nAttempting to infer types for remaining unknown transactions...")
            
            # If we have a positive quantity and price, it's likely a buy
            buy_mask = (still_unknown & 
                       (df["quantity"] > 0) & 
                       (df["price"] > 0) & 
                       (~df["asset"].isin(["USD", "USDC"])))
            mapped[buy_mask] = "buy"
            
            # If we have a negative quantity and price, it's likely a sell
            sell_mask = (still_unknown & 
                        (df["quantity"] < 0) & 
                        (df["price"] > 0) & 
                        (~df["asset"].isin(["USD", "USDC"])))
            mapped[sell_mask] = "sell"
            
            # If it's a USD/USDC transaction with positive quantity, it's likely a deposit
            deposit_mask = (still_unknown & 
                          (df["quantity"] > 0) & 
                          (df["asset"].isin(["USD", "USDC"])))
            mapped[deposit_mask] = "deposit"
            
            # If it's a USD/USDC transaction with negative quantity, it's likely a withdrawal
            withdrawal_mask = (still_unknown & 
                             (df["quantity"] < 0) & 
                             (df["asset"].isin(["USD", "USDC"])))
            mapped[withdrawal_mask] = "withdrawal"
            
            print("\nAfter type inference:")
            print(mapped.value_counts())
    
    # Check for any remaining unknown types
    unknowns = raw_types[mapped == "unknown"].unique()
    if len(unknowns) > 0:
        print("\n⚠️ Unknown transaction types found:")
        for u in unknowns:
            if u:  # Only print non-empty unknown types
                print(f"  - '{u}' (consider adding to TRANSACTION_TYPE_MAP)")
            else:
                print("  - Empty/missing type field found")
    
    df["type"] = mapped
    print("\n=== Transaction Type Normalization Complete ===")
    print(f"Final transaction type distribution:")
    print(df["type"].value_counts())
    print("\n")
    return df

def normalize_numeric_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Clean numeric columns and preserve exact values from source data."""
    numeric_cols = ["quantity", "price", "subtotal", "total", "fees"]
    
    # Convert all numeric columns to float, preserving exact values
    for col in numeric_cols:
        if col in df.columns:
            # For quantity column, preserve negative values for sells
            if col == "quantity":
                # Convert to numeric, preserving negative values
                df[col] = pd.to_numeric(df[col].astype(str).str.replace('$', '').str.replace(',', ''), errors='coerce')
                # Make sure quantities are negative for sells
                df.loc[df["type"] == "sell", col] = -df.loc[df["type"] == "sell", col].abs()
            else:
                # For other columns, convert to numeric
                df[col] = pd.to_numeric(df[col].astype(str).str.replace('$', '').str.replace(',', ''), errors='coerce')
            
            # Only make fees positive
            if col == "fees":
                df[col] = df[col].abs()
                # Fill NaN fees with 0
                df[col] = df[col].fillna(0)
            else:
                # For other columns, preserve NaN values
                # This ensures we don't accidentally fill in missing values with 0
                pass
    
    return df

def normalize_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    Apply all normalization steps: transaction type mapping,
    timestamp conversion, numeric cleaning, and filtering out non-transactional rows.
    """
    df = normalize_transaction_types(df)
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    df = normalize_numeric_columns(df)
    # Filter out rows that are not real transactions (like summaries)
    df = df[df["type"] != "non_transactional"]
    return df
