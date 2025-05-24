import pandas as pd
from app.commons.utils import clean_numeric_column
from typing import Dict, Set
import logging

# Configure logging
logger = logging.getLogger(__name__)

# Define canonical transaction types for validation
CANONICAL_TYPES: Set[str] = {
    'buy', 'sell', 'deposit', 'withdrawal', 'transfer_in', 'transfer_out',
    'staking_reward', 'dividend', 'interest', 'fee', 'tax', 'swap', 'trade',
    'rebate', 'reward', 'staking', 'unstaking', 'fee_adjustment', 'transfer',
    'non_transactional', 'unknown'
}

# Expanded mapping for raw transaction types to our canonical set.
TRANSACTION_TYPE_MAP: Dict[str, str] = {
    # === BINANCE US ===
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
    'Staking Rewards': 'staking_reward',  # Most common Binance type
    'USD Deposit': 'deposit',
    'Crypto Deposit': 'transfer_in',
    'Crypto Withdrawal': 'transfer_out',
    
    # === COINBASE ===
    'Receive': 'transfer_in',
    'Send': 'transfer_out', 
    'Buy': 'buy',
    'Sell': 'sell',
    'Rewards Income': 'staking_reward',
    'Coinbase Earn': 'reward',
    'Learning Reward': 'reward',
    'Staking Income': 'staking_reward',  # Most common Coinbase type
    'Advanced Trade Buy': 'buy',
    'Advanced Trade Sell': 'sell',
    'Convert': 'swap',
    'Inflation Reward': 'staking_reward',  # Common Coinbase type
    'Reward Income': 'staking_reward',
    'Exchange Deposit': 'deposit',
    'Exchange Withdrawal': 'withdrawal',
    'Withdrawal': 'withdrawal',
    'Deposit': 'deposit',
    
    # === GEMINI ===
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
    'Interest Credit': 'staking_reward',  # Gemini staking
    'Administrative Debit': 'transfer_out',
    'Redeem': 'unstaking',

    # === INTERACTIVE BROKERS ===
    'Buy': 'buy',
    'Sell': 'sell',
    'Deposit': 'deposit',
    'Withdrawal': 'withdrawal',
    'Dividend': 'dividend',
    'Credit Interest': 'interest',
    'Other Fee': 'fee',
    'Foreign Tax Withholding': 'tax',
    'Commission Adjustment': 'fee_adjustment',
    'Cash Transfer': 'transfer',
    'Electronic Fund Transfer': 'deposit',
    'Electronic Fund Transfer (Regular Contribution)': 'deposit',
    'Disbursement Initiated by Account Closure': 'withdrawal',
    'Disbursement Initiated by Nash Collins (Refund of excess from a Roth-current year, age Under 59.5)': 'withdrawal',
    'Adjustment: Deposit Advance (First 1,000.00 of 6,000.00 Deposit)': 'deposit',
    'Cancellation (First 1,000.00 of 6,000.00 Deposit)': 'withdrawal',

    # === GENERIC MAPPINGS ===
    # Deposits/Withdrawals
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

    # Transfers
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

    # Staking/Rewards
    "staking income": "staking_reward",
    "Staking Income": "staking_reward",
    "reward income": "staking_reward",
    "Reward Income": "staking_reward",
    "interest credit": "staking_reward",
    "Interest Credit": "staking_reward",
    "inflation reward": "staking_reward",
    "Inflation Reward": "staking_reward",

    # Conversions/Swaps
    "convert": "swap",
    "Convert": "swap",
    "conversion": "swap",
    "Conversion": "swap",
    "redeem": "swap",
    "Redeem": "swap",

    # Non-transactional (to be filtered out)
    "monthly interest summary": "non_transactional",
    "Monthly Interest Summary": "non_transactional",

    # Fallback for empty strings
    "": "unknown",
}

def validate_canonical_types() -> bool:
    """Validate that all mapped types are in the canonical set."""
    mapped_types = set(TRANSACTION_TYPE_MAP.values())
    invalid_types = mapped_types - CANONICAL_TYPES
    if invalid_types:
        logger.warning(f"Invalid canonical types found in mapping: {invalid_types}")
        return False
    return True

def get_institution_from_columns(df: pd.DataFrame) -> str:
    """Detect institution based on column patterns."""
    columns = set(df.columns)
    
    if 'Operation' in columns and 'Primary Asset' in columns:
        return 'binance_us'
    elif 'Transaction Type' in columns and 'Asset' in columns and 'Quantity Transacted' in columns:
        return 'coinbase'
    elif 'Symbol' in columns and ('Gross Amount' in columns or 'Net Amount' in columns):
        return 'interactive_brokers'
    elif 'Type' in columns and ('Time (UTC)' in columns or 'Specification' in columns):
        return 'gemini'
    else:
        return 'unknown'

def normalize_transaction_types(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalize the 'type' column to a canonical set using TRANSACTION_TYPE_MAP.
    Any unmapped types are flagged as 'unknown'.
    """
    logger.info("Starting Transaction Type Normalization")
    logger.info(f"Total transactions to process: {len(df)}")
    
    # Handle empty DataFrame
    if df.empty:
        logger.info("Empty DataFrame provided, returning empty result")
        return df
    
    # Check if type column exists
    if 'type' not in df.columns:
        logger.error("No 'type' column found in DataFrame")
        raise KeyError("DataFrame must contain a 'type' column")
    
    # Validate our mapping first
    if not validate_canonical_types():
        logger.error("Invalid canonical types detected in mapping!")
    
    # Detect institution for better error reporting
    institution = get_institution_from_columns(df)
    logger.info(f"Detected institution: {institution}")
    
    # Debug print raw transaction types
    logger.info("Raw transaction types before normalization:")
    raw_types = df["type"].fillna("").astype(str).str.strip()
    type_counts = raw_types.value_counts()
    for type_name, count in type_counts.head(10).items():
        logger.info(f"  {type_name}: {count}")
    if len(type_counts) > 10:
        logger.info(f"  ... and {len(type_counts) - 10} more types")
    
    # Initialize mapped types as unknown
    mapped = pd.Series("unknown", index=df.index)
    
    # Handle Binance specific cases first
    if any(col.lower() == "operation" for col in df.columns):
        operation_col = next(col for col in df.columns if col.lower() == "operation")
        logger.info("Processing Binance operations")
        operations = df[operation_col].fillna("").astype(str).str.strip()
        
        # Create a mask for crypto transfers
        crypto_deposit_mask = (operations.str.lower() == "crypto deposit")
        crypto_withdrawal_mask = (operations.str.lower() == "crypto withdrawal")
        
        # Map crypto transfers
        mapped[crypto_deposit_mask] = "transfer_in"
        mapped[crypto_withdrawal_mask] = "transfer_out"
        
        logger.info(f"Mapped {crypto_deposit_mask.sum()} crypto deposits and {crypto_withdrawal_mask.sum()} crypto withdrawals")
    
    # Handle Coinbase specific cases
    if "Transaction Type" in df.columns:
        logger.info("Processing Coinbase transaction types")
        coinbase_types = df["Transaction Type"].fillna("").astype(str).str.strip()
        
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
        
        logger.info(f"Mapped {transfer_in_mask.sum()} transfer ins and {transfer_out_mask.sum()} transfer outs")
    
    # Create case-insensitive mapping by converting all keys to lowercase
    case_insensitive_map = {k.lower(): v for k, v in TRANSACTION_TYPE_MAP.items()}
    
    # Map remaining transaction types (excluding already mapped transfers)
    remaining_mask = mapped == "unknown"
    if remaining_mask.any():
        # For remaining transactions, try to map from the type column
        raw_types_lower = raw_types[remaining_mask].str.lower()
        mapped[remaining_mask] = raw_types_lower.map(case_insensitive_map).fillna("unknown")
        
        logger.info(f"Mapped {(mapped != 'unknown').sum()} transactions using general mapping")
        
        # For any remaining unknowns, try to infer from other columns
        still_unknown = mapped == "unknown"
        if still_unknown.any():
            logger.info(f"Attempting to infer types for {still_unknown.sum()} remaining unknown transactions...")
            
            # Enhanced inference logic - only if we have the required columns
            if all(col in df.columns for col in ['quantity', 'price', 'asset']):
                # If we have a positive quantity and price, it's likely a buy
                buy_mask = (still_unknown & 
                           (df["quantity"] > 0) & 
                           (df["price"] > 0) & 
                           (~df["asset"].isin(["USD", "USDC", "USDT", "DAI", "BUSD"])))
                mapped[buy_mask] = "buy"
                
                # If we have a negative quantity and price, it's likely a sell
                sell_mask = (still_unknown & 
                            (df["quantity"] < 0) & 
                            (df["price"] > 0) & 
                            (~df["asset"].isin(["USD", "USDC", "USDT", "DAI", "BUSD"])))
                mapped[sell_mask] = "sell"
                
                # If it's a stablecoin/USD transaction with positive quantity, it's likely a deposit
                deposit_mask = (still_unknown & 
                              (df["quantity"] > 0) & 
                              (df["asset"].isin(["USD", "USDC", "USDT", "DAI", "BUSD"])))
                mapped[deposit_mask] = "deposit"
                
                # If it's a stablecoin/USD transaction with negative quantity, it's likely a withdrawal
                withdrawal_mask = (still_unknown & 
                                 (df["quantity"] < 0) & 
                                 (df["asset"].isin(["USD", "USDC", "USDT", "DAI", "BUSD"])))
                mapped[withdrawal_mask] = "withdrawal"
                
                inferred_count = buy_mask.sum() + sell_mask.sum() + deposit_mask.sum() + withdrawal_mask.sum()
                logger.info(f"Inferred {inferred_count} transaction types from data patterns")
    
    # Check for any remaining unknown types
    unknowns = raw_types[mapped == "unknown"].unique()
    if len(unknowns) > 0:
        logger.warning(f"Found {len(unknowns)} unknown transaction types:")
        for u in unknowns:
            if u:  # Only print non-empty unknown types
                count = (raw_types == u).sum()
                logger.warning(f"  - '{u}' ({count} occurrences) - consider adding to TRANSACTION_TYPE_MAP")
            else:
                logger.warning("  - Empty/missing type field found")
    
    df["type"] = mapped
    logger.info("Transaction Type Normalization Complete")
    
    # Final validation
    final_counts = df["type"].value_counts()
    logger.info("Final transaction type distribution:")
    for type_name, count in final_counts.items():
        logger.info(f"  {type_name}: {count}")
    
    # Check for invalid canonical types
    invalid_final_types = set(final_counts.index) - CANONICAL_TYPES
    if invalid_final_types:
        logger.error(f"Invalid final transaction types: {invalid_final_types}")
    
    return df

def normalize_numeric_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Clean numeric columns and preserve exact values from source data."""
    numeric_cols = ["quantity", "price", "subtotal", "total", "fees"]
    
    logger.info("Normalizing numeric columns")
    
    # Convert all numeric columns to float, preserving exact values
    for col in numeric_cols:
        if col in df.columns:
            original_nulls = df[col].isnull().sum()
            
            # For quantity column, preserve negative values for sells
            if col == "quantity":
                # Convert to numeric, preserving negative values
                df[col] = pd.to_numeric(df[col].astype(str).str.replace('$', '').str.replace(',', ''), errors='coerce')
                # Make sure quantities are negative for sells
                sell_mask = df["type"] == "sell"
                if sell_mask.any():
                    df.loc[sell_mask, col] = -df.loc[sell_mask, col].abs()
                    logger.info(f"Made {sell_mask.sum()} sell quantities negative")
            else:
                # For other columns, convert to numeric
                df[col] = pd.to_numeric(df[col].astype(str).str.replace('$', '').str.replace(',', ''), errors='coerce')
            
            # Handle fees specially
            if col == "fees":
                df[col] = df[col].abs()  # Fees should always be positive
                df[col] = df[col].fillna(0)  # Fill NaN fees with 0
                logger.info(f"Normalized {col}: filled {original_nulls} null values with 0")
            else:
                new_nulls = df[col].isnull().sum()
                if new_nulls > original_nulls:
                    logger.warning(f"Column {col}: {new_nulls - original_nulls} values became null during conversion")
    
    return df

def validate_normalized_data(df: pd.DataFrame) -> bool:
    """Validate the normalized data for common issues."""
    issues = []
    
    # Check for required columns
    required_cols = ['timestamp', 'type', 'asset', 'quantity']
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        issues.append(f"Missing required columns: {missing_cols}")
    
    # Check for invalid transaction types
    if 'type' in df.columns:
        invalid_types = set(df['type'].unique()) - CANONICAL_TYPES
        if invalid_types:
            issues.append(f"Invalid transaction types: {invalid_types}")
    
    # Check for null timestamps
    if 'timestamp' in df.columns:
        null_timestamps = df['timestamp'].isnull().sum()
        if null_timestamps > 0:
            issues.append(f"{null_timestamps} transactions have null timestamps")
    
    # Check for null assets
    if 'asset' in df.columns:
        null_assets = df['asset'].isnull().sum()
        if null_assets > 0:
            issues.append(f"{null_assets} transactions have null assets")
    
    # Check for zero quantities in non-fee transactions
    if 'quantity' in df.columns and 'type' in df.columns:
        zero_qty_mask = (df['quantity'] == 0) & (~df['type'].isin(['fee', 'tax', 'fee_adjustment']))
        zero_qty_count = zero_qty_mask.sum()
        if zero_qty_count > 0:
            issues.append(f"{zero_qty_count} non-fee transactions have zero quantity")
    
    if issues:
        logger.warning("Data validation issues found:")
        for issue in issues:
            logger.warning(f"  - {issue}")
        return False
    else:
        logger.info("Data validation passed")
        return True

def normalize_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    Apply all normalization steps: transaction type mapping,
    timestamp conversion, numeric cleaning, and filtering out non-transactional rows.
    """
    logger.info("Starting complete data normalization")
    
    # Handle empty DataFrame
    if df.empty:
        logger.info("Empty DataFrame provided, returning empty result")
        return df
    
    # Step 1: Normalize transaction types
    df = normalize_transaction_types(df)
    
    # Step 2: Normalize timestamps
    logger.info("Normalizing timestamps")
    if 'timestamp' in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
        null_timestamps = df["timestamp"].isnull().sum()
        if null_timestamps > 0:
            logger.warning(f"{null_timestamps} timestamps could not be parsed")
    
    # Step 3: Normalize numeric columns
    df = normalize_numeric_columns(df)
    
    # Step 4: Filter out non-transactional rows
    before_filter = len(df)
    df = df[df["type"] != "non_transactional"]
    after_filter = len(df)
    if before_filter != after_filter:
        logger.info(f"Filtered out {before_filter - after_filter} non-transactional rows")
    
    # Step 5: Validate the normalized data
    validate_normalized_data(df)
    
    logger.info(f"Data normalization complete. Final dataset: {len(df)} transactions")
    return df
