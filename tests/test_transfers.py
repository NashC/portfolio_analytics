import pandas as pd
from datetime import datetime
from app.ingestion.transfers import reconcile_transfers

def test_reconcile_transfers():
    # Create a sample DataFrame with one transfer_out and one matching transfer_in.
    data = {
        "timestamp": [
            datetime(2023, 1, 1, 12, 0, 0),
            datetime(2023, 1, 1, 12, 3, 0),
            datetime(2023, 1, 1, 13, 0, 0)  # Non-transfer event, for control
        ],
        "type": [
            "transfer_out",
            "transfer_in",
            "buy"
        ],
        "asset": [
            "BTC",
            "BTC",
            "BTC"
        ],
        "quantity": [
            0.5,
            0.5,
            1.0
        ],
        "institution": [  # Add institution column
            "binanceus",
            "coinbase",
            "coinbase"
        ]
    }
    df = pd.DataFrame(data)
    reconciled = reconcile_transfers(df)
    
    # Check that both transfer events have been assigned a transfer_id.
    transfer_events = reconciled[reconciled["type"].isin(["transfer_out", "transfer_in"])]
    assert transfer_events["transfer_id"].nunique() == 1, "Expected one unique transfer_id"
    # Ensure the buy event remains untagged.
    assert pd.isna(reconciled.loc[2, "transfer_id"])
