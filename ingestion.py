import os
import glob
import pandas as pd
import yaml
from typing import Dict, Optional


def load_schema_config(config_path: str) -> Dict:
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


def parse_timestamp(row: pd.Series, date_col: str, time_col: Optional[str] = None) -> pd.Timestamp:
    if time_col and time_col in row and pd.notna(row[time_col]):
        return pd.to_datetime(f"{row[date_col]} {row[time_col]}")
    return pd.to_datetime(row[date_col])


def ingest_csv(file_path: str, mapping: Dict, file_type: str = "") -> pd.DataFrame:
    df = pd.read_csv(file_path)

    # Rename columns using reverse mapping (CSV column → standard name)
    rename_map = {v: k for k, v in mapping.items() if v}
    df = df.rename(columns=rename_map)

    # Timestamp logic
    if "timestamp" not in df.columns and "timestamp" in mapping:
        date_col = mapping.get("timestamp", "")
        time_col = mapping.get("time", "")
        if date_col in df.columns and time_col:
            df["timestamp"] = df.apply(lambda row: parse_timestamp(row, date_col, time_col), axis=1)
        elif date_col in df.columns:
            df["timestamp"] = pd.to_datetime(df[date_col], errors='coerce')

    # Inject constant fields (like account_owner)
    for field, value in mapping.items():
        if field not in df.columns and value and not (value in df.columns):
            df[field] = value

    df["file_type"] = file_type
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
                return institution, None, entry["mapping"]
        # Check for nested mappings (e.g., gemini with staking and transactions)
        elif isinstance(entry, dict):
            for sub_key, sub_entry in entry.items():
                if isinstance(sub_entry, dict) and "file_pattern" in sub_entry:
                    if file_name == sub_entry["file_pattern"]:
                        return institution, sub_key, sub_entry["mapping"]
    return None, None, None

def process_transactions(data_dir: str, config_path: str) -> pd.DataFrame:
    config = load_schema_config(config_path)
    all_files = [f for f in os.listdir(data_dir) if f.endswith(".csv")]
    all_transactions = []
    for file_name in all_files:
        file_path = os.path.join(data_dir, file_name)
        institution, subtype, mapping = match_file_to_mapping(file_name, config)
        if mapping:
            file_type = f"{institution}_{subtype}" if subtype else institution
            df = ingest_csv(file_path, mapping, file_type=file_type)
            df["user_id"] = 1
            df["institution"] = institution
            all_transactions.append(df)
        else:
            print(f"⚠️ Skipping unrecognized file: {file_name}")
    if all_transactions:
        transactions = pd.concat(all_transactions, ignore_index=True)
        return transactions
    else:
        print("❌ No transactions processed.")
        return pd.DataFrame()