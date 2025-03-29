import pandas as pd
from utils import clean_numeric_column

# Expanded mapping for raw transaction types to our canonical set.
TRANSACTION_TYPE_MAP = {
    # BUY / SELL
    "buy": "buy",
    "advanced trade buy": "buy",
    "sell": "sell",

    # DEPOSIT / WITHDRAWAL
    "deposit": "deposit",
    "exchange deposit": "deposit",
    "withdraw": "withdrawal",
    "withdrawal": "withdrawal",
    "exchange withdrawal": "withdrawal",

    # TRANSFERS
    "receive": "transfer_in",
    "credit": "transfer_in",
    "send": "transfer_out",
    "debit": "transfer_out",
    "administrative debit": "transfer_out",
    "distribution": "transfer_in",

    # STAKING / REWARDS
    "staking income": "staking_reward",
    "reward income": "staking_reward",
    "interest credit": "staking_reward",
    "inflation reward": "staking_reward",

    # CONVERSIONS / SWAPS
    "convert": "swap",
    "conversion": "swap",
    "redeem": "swap",

    # NON-TRANSACTIONAL (to be skipped or tagged)
    "monthly interest summary": "non_transactional",

    # Fallback for empty strings, etc.
    "": "unknown",
}

def normalize_transaction_types(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalize the 'type' column to a canonical set using TRANSACTION_TYPE_MAP.
    Any unmapped types are flagged as 'unknown'.
    """
    raw_types = df["type"].fillna("").astype(str).str.strip().str.lower()
    mapped = raw_types.map(TRANSACTION_TYPE_MAP)
    
    unknowns = raw_types[mapped.isna()].unique()
    if len(unknowns) > 0:
        print("⚠️ Unknown transaction types found:")
        for u in unknowns:
            print(f"  - '{u}' (consider adding to TRANSACTION_TYPE_MAP)")
    
    df["type"] = mapped.fillna("unknown")
    return df

def normalize_numeric_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Clean numeric columns (price, fees, quantity) using a utility function.
    """
    for col in ["price", "fees", "quantity"]:
        if col in df.columns:
            df[col] = clean_numeric_column(df[col])
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
