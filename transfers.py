import pandas as pd
import uuid
from datetime import timedelta

def reconcile_transfers(df: pd.DataFrame, time_tolerance=timedelta(hours=1), quantity_tolerance=0.001) -> pd.DataFrame:
    """
    Reconcile transfer events by pairing 'transfer_out' and 'transfer_in'.
    
    If available, first attempt to match using the 'Tx Hash' column. If a match is found,
    assign the same transfer_id to both events. For remaining unmatched transfers, 
    match based on asset, quantity, and timestamp proximity.
    """
    df = df.copy()
    df['transfer_id'] = None

    # Check if "Tx Hash" column is present
    tx_hash_available = "Tx Hash" in df.columns

    # Separate transfer events.
    transfers_out = df[df["type"] == "transfer_out"]
    transfers_in = df[df["type"] == "transfer_in"]

    # First, try matching based on "Tx Hash" if available.
    if tx_hash_available:
        in_by_hash = transfers_in.set_index("Tx Hash")
        for out_idx, out_row in transfers_out.iterrows():
            tx_hash = out_row.get("Tx Hash")
            if pd.notnull(tx_hash) and tx_hash in in_by_hash.index:
                in_candidate = in_by_hash.loc[tx_hash]
                # in_candidate may be multiple rows; pick the first unmatched one.
                if isinstance(in_candidate, pd.DataFrame):
                    in_candidate = in_candidate[in_candidate['transfer_id'].isna()]
                    if not in_candidate.empty:
                        candidate_idx = in_candidate.index[0]
                    else:
                        candidate_idx = None
                else:
                    candidate_idx = in_candidate.name if pd.isna(in_candidate['transfer_id']) else None
                if candidate_idx is not None:
                    transfer_id = str(uuid.uuid4())
                    df.at[out_idx, 'transfer_id'] = transfer_id
                    df.at[candidate_idx, 'transfer_id'] = transfer_id

        # Recalculate transfers_in as those still unmatched.
        transfers_in = df[(df["type"] == "transfer_in") & (df['transfer_id'].isna())]

    # For remaining unmatched transfers, match by asset, quantity, and timestamp.
    for out_idx, out_row in df[(df["type"] == "transfer_out") & (df['transfer_id'].isna())].iterrows():
        candidates = df[(df["type"] == "transfer_in") & (df['transfer_id'].isna())]
        candidates = candidates[candidates["asset"] == out_row["asset"]]
        candidates = candidates[abs(candidates["quantity"] - out_row["quantity"]) <= quantity_tolerance]
        candidates = candidates[abs(candidates["timestamp"] - out_row["timestamp"]) <= time_tolerance]
    
    return df

