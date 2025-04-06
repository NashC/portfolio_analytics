import pandas as pd
from utils import clean_numeric_column

# Expanded mapping for raw transaction types to our canonical set.
TRANSACTION_TYPE_MAP = {
    # BUY / SELL
    "buy": "buy",
    "Buy": "buy",
    "advanced trade buy": "buy",
    "Advanced Trade Buy": "buy",
    "sell": "sell",
    "Sell": "sell",
    "advanced trade sell": "sell",
    "Advanced Trade Sell": "sell",
    "trade": "sell",  # Coinbase uses "trade" for sells
    "Trade": "sell",

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
    # Convert raw types to lowercase
    raw_types = df["type"].fillna("").astype(str).str.strip()
    
    # Create case-insensitive mapping by converting all keys to lowercase
    case_insensitive_map = {k.lower(): v for k, v in TRANSACTION_TYPE_MAP.items()}
    mapped = raw_types.str.lower().map(case_insensitive_map)
    
    unknowns = raw_types[mapped.isna()].unique()
    if len(unknowns) > 0:
        print("⚠️ Unknown transaction types found:")
        for u in unknowns:
            print(f"  - '{u}' (consider adding to TRANSACTION_TYPE_MAP)")
    
    df["type"] = mapped.fillna("unknown")
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
