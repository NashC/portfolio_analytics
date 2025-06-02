import pandas as pd
import tempfile
import os
from app.ingestion.loader import ingest_csv

def test_ingest_csv():
    # Create a temporary CSV file with sample data.
    data = {
        "Date": ["2023-01-01", "2023-01-02"],
        "Ticker": ["AAPL", "AAPL"],
        "Transaction Type": ["buy", "sell"],
        "Quantity": [10, 5],
        "Price": [150, 155],
        "Fees": [1, 1],
        "Currency": ["USD", "USD"]
    }
    df = pd.DataFrame(data)
    temp_csv = tempfile.NamedTemporaryFile(delete=False, suffix=".csv")
    df.to_csv(temp_csv.name, index=False)
    
    mapping = {
        "timestamp": "Date",
        "asset": "Ticker",
        "type": "Transaction Type",
        "quantity": "Quantity",
        "price": "Price",
        "fees": "Fees",
        "currency": "Currency"
    }
    
    result = ingest_csv(temp_csv.name, mapping)
    assert "timestamp" in result.columns
    assert "asset" in result.columns
    os.remove(temp_csv.name)
