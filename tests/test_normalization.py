import pandas as pd
from app.ingestion.normalization import normalize_transaction_types

def test_normalize_transaction_types():
    raw = pd.DataFrame({
        "type": ["Buy", "SELL", "withdraw", "Staking", "Receive", "FLIP"],
        "quantity": [1.0, -1.0, -0.5, 0.1, 0.2, 0.3],
        "price": [100.0, 100.0, 0.0, 0.0, 0.0, 50.0],
        "asset": ["BTC", "BTC", "USD", "ETH", "BTC", "UNKNOWN"]
    })
    normalized = normalize_transaction_types(raw)
    expected = ["buy", "sell", "withdrawal", "staking_reward", "transfer_in", "buy"]
    assert normalized["type"].tolist() == expected
