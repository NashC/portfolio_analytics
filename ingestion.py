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
