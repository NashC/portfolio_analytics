import pandas as pd
import uuid
from datetime import timedelta

def reconcile_transfers(
    df: pd.DataFrame, 
    time_tolerance: timedelta = timedelta(minutes=5), 
    quantity_tolerance: float = 0.001
) -> pd.DataFrame:
    """
    Reconcile transfers by pairing transfer_out and transfer_in events.
    
    For each transfer_out event, this function searches for a matching transfer_in 
    event with the same asset, nearly equal quantity (within quantity_tolerance), 
    and occurring within time_tolerance. If a match is found, both events are assigned
    the same unique transfer_id.
    
    Args:
        df: DataFrame with normalized transactions.
        time_tolerance: Maximum time difference allowed between paired transfers.
        quantity_tolerance: Maximum allowed difference in quantity between paired transfers.
    
    Returns:
        DataFrame with an added 'transfer_id' column for paired transfers.
    """
    # Make a copy to avoid mutating the original DataFrame.
    df = df.copy()
    df['transfer_id'] = None

    # Filter the transfer events.
    transfers_out = df[df['type'] == 'transfer_out']
    transfers_in = df[df['type'] == 'transfer_in']

    # Iterate over each transfer_out event.
    for out_idx, out_row in transfers_out.iterrows():
        # Find candidate transfer_in events with matching asset,
        # quantity within tolerance, and timestamp within tolerance.
        candidates = transfers_in[
            (transfers_in['asset'] == out_row['asset']) &
            (abs(transfers_in['quantity'] - out_row['quantity']) <= quantity_tolerance) &
            (abs(transfers_in['timestamp'] - out_row['timestamp']) <= time_tolerance)
        ]
        if not candidates.empty:
            # Select the candidate with the smallest time difference.
            time_diffs = abs(candidates['timestamp'] - out_row['timestamp'])
            candidate_idx = time_diffs.idxmin()
            transfer_id = str(uuid.uuid4())
            df.at[out_idx, 'transfer_id'] = transfer_id
            df.at[candidate_idx, 'transfer_id'] = transfer_id
            # Remove the matched candidate to avoid re-matching.
            transfers_in = transfers_in.drop(candidate_idx)

    return df
