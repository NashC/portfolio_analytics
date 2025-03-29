import pandas as pd
from normalization import normalize_transaction_types

def test_normalize_transaction_types():
    raw = pd.DataFrame({"type": ["Buy", "SELL", "withdraw", "Staking", "Receive", "FLIP"]})
    normalized = normalize_transaction_types(raw)
    expected = ["buy", "sell", "withdrawal", "staking_reward", "transfer_in", "unknown"]
    assert normalized["type"].tolist() == expected
