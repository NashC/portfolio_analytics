import pandas as pd

def clean_numeric_column(series: pd.Series) -> pd.Series:
    """
    Clean a numeric column by removing symbols and converting to float.
    Invalid strings are coerced to NaN.
    """
    cleaned = (
        series.astype(str)
              .str.replace(r"[^\d\.\-eE]", "", regex=True)  # allow scientific notation too
              .replace("", "0")
    )
    return pd.to_numeric(cleaned, errors="coerce")

def format_currency(value: float) -> str:
    """Format a number as currency with dollar sign and commas"""
    return f"${value:,.2f}"

def format_number(value: float) -> str:
    """Format a number with commas and 2 decimal places"""
    return f"{value:,.2f}"
