import pandas as pd

def normalize_transaction_types(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalize transaction types to a unified set.
    
    Args:
        df: DataFrame with a 'type' column.
        
    Returns:
        DataFrame with normalized 'type' values.
    """
    type_mapping = {
        "buy": "buy",
        "purchase": "buy",
        "sell": "sell",
        "dividend": "dividend",
        "deposit": "deposit",
        "withdrawal": "withdrawal",
        "transfer_in": "transfer_in",
        "transfer_out": "transfer_out",
        "staking_reward": "staking_reward",
        "airdrop": "airdrop",
        # Add more mappings as needed.
    }
    df["type"] = df["type"].str.lower().map(type_mapping).fillna(df["type"].str.lower())
    return df

def normalize_data(df: pd.DataFrame) -> pd.DataFrame:
    df = normalize_transaction_types(df)

    # Ensure 'timestamp' column is datetime
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")

    return df


# Mapping from raw transaction types (case-insensitive) to unified categories
TRANSACTION_TYPE_MAP = {
    "buy": "buy",
    "purchase": "buy",
    "fill": "buy",
    "sell": "sell",
    "sell to": "sell",
    "withdrawal": "withdrawal",
    "withdraw": "withdrawal",
    "send": "transfer_out",
    "receive": "transfer_in",
    "deposit": "deposit",
    "staking reward": "staking_reward",
    "staking": "staking_reward",
    "interest": "staking_reward",
    "reward": "staking_reward",
    "dividend": "dividend",
    "airdrop": "airdrop",
    "conversion": "swap",
    "swap": "swap",
    # You can add more as needed
}

def normalize_transaction_types(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalizes the 'type' column of a transaction DataFrame using TRANSACTION_TYPE_MAP.

    Args:
        df: A pandas DataFrame with a 'type' column containing raw transaction labels.

    Returns:
        The same DataFrame with a normalized 'type' column.
    """
    df["type"] = (
        df["type"]
        .astype(str)
        .str.lower()
        .map(TRANSACTION_TYPE_MAP)
        .fillna("unknown")
    )
    return df


def normalize_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    Apply all normalization steps to the transaction data.

    Args:
        df: A pandas DataFrame of raw or ingested transactions.

    Returns:
        A normalized DataFrame.
    """
    df = normalize_transaction_types(df)
    # You can add more steps here later (e.g., currency normalization, amount validation)
    return df
