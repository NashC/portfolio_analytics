import pandas as pd
import uuid
from datetime import timedelta

def reconcile_transfers(df: pd.DataFrame, time_tolerance=timedelta(days=1), quantity_tolerance=0.1) -> pd.DataFrame:
    """
    Reconcile transfer events by pairing 'transfer_out' and 'transfer_in'.
    
    Matching strategy:
    1. First try matching using transaction hash if available
    2. Then try matching based on exchange pairs (e.g., binanceus -> coinbase)
    3. Finally fall back to matching based on asset, quantity, and timestamp proximity
    
    Note: All Binance US transfers are assumed to be to/from Coinbase and vice versa.
    """
    print("\n=== Starting Transfer Reconciliation ===")
    print(f"Total transactions: {len(df)}")
    print(f"Transfer types: {df['type'].value_counts()}")
    print(f"Institutions: {df['institution'].value_counts()}")
    
    df = df.copy()
    
    # Only ensure transfer_in quantities are positive
    df.loc[df['type'] == 'transfer_in', 'quantity'] = abs(df.loc[df['type'] == 'transfer_in', 'quantity'])
    
    df['transfer_id'] = None
    df['matching_institution'] = None
    df['matching_date'] = None
    df['cost_basis'] = 0.0  # Initialize cost basis
    df['cost_basis_per_unit'] = 0.0  # Initialize cost basis per unit

    # Check if "Tx Hash" column is present
    tx_hash_available = "Tx Hash" in df.columns
    print(f"\nTransaction hash available: {tx_hash_available}")

    # Separate transfer events
    transfers_out = df[df["type"] == "transfer_out"]
    transfers_in = df[df["type"] == "transfer_in"]
    print(f"\nTransfer counts:")
    print(f"Transfer out: {len(transfers_out)}")
    print(f"Transfer in: {len(transfers_in)}")

    def match_transfer_pair(send, receive):
        # Base quantity tolerance
        base_tolerance = 0.0001
        
        # For larger transfers, use percentage-based tolerance (1% of transfer amount)
        quantity_tolerance = max(base_tolerance, abs(send['quantity']) * 0.01)
        
        # Check if quantities match within tolerance
        quantity_matches = abs(abs(send['quantity']) - abs(receive['quantity'])) <= quantity_tolerance
        
        # For ETH/ETH2 internal Coinbase transfers, match if:
        # 1. Both are on Coinbase
        # 2. One is ETH and one is ETH2
        # 3. Quantities match
        # 4. Same date
        if (send['institution'] == 'coinbase' and receive['institution'] == 'coinbase' and
            {send['asset'], receive['asset']} == {'ETH', 'ETH2'} and
            quantity_matches and
            send['timestamp'].date() == receive['timestamp'].date()):
            return True
        
        # For regular transfers between different institutions
        return (send['asset'] == receive['asset'] and
                quantity_matches and
                abs((send['timestamp'] - receive['timestamp']).total_seconds()) <= 86400)  # Within 24 hours

    # First, try matching based on "Tx Hash" if available
    if tx_hash_available:
        in_by_hash = transfers_in.set_index("Tx Hash")
        for out_idx, out_row in transfers_out.iterrows():
            tx_hash = out_row.get("Tx Hash")
            if pd.notnull(tx_hash) and tx_hash in in_by_hash.index:
                in_candidate = in_by_hash.loc[tx_hash]
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
                    # Store matching info and transfer cost basis
                    df.at[out_idx, 'matching_institution'] = df.at[candidate_idx, 'institution']
                    df.at[out_idx, 'matching_date'] = df.at[candidate_idx, 'timestamp'].strftime('%Y-%m-%d')
                    df.at[candidate_idx, 'matching_institution'] = df.at[out_idx, 'institution']
                    df.at[candidate_idx, 'matching_date'] = df.at[out_idx, 'timestamp'].strftime('%Y-%m-%d')
                    
                    # Transfer cost basis
                    out_quantity = abs(float(out_row['quantity']))
                    if out_quantity > 0:
                        out_cost_basis = abs(float(out_row.get('cost_basis', 0)))
                        out_cost_basis_per_unit = out_cost_basis / out_quantity
                        df.at[candidate_idx, 'cost_basis'] = out_cost_basis
                        df.at[candidate_idx, 'cost_basis_per_unit'] = out_cost_basis_per_unit

        # Recalculate transfers_in as those still unmatched
        transfers_in = df[(df["type"] == "transfer_in") & (df['transfer_id'].isna())]

    # Handle Coinbase <-> Binance US transfers
    for institution_pair in [('binanceus', 'coinbase'), ('coinbase', 'binanceus')]:
        from_inst, to_inst = institution_pair
        unmatched_transfers = transfers_out[
            (transfers_out['institution'].str.lower() == from_inst) & 
            (transfers_out['transfer_id'].isna())
        ]
        
        # Group transfers by date and asset
        grouped_transfers = unmatched_transfers.groupby(['timestamp', 'asset'])
        
        for (date, asset), group in grouped_transfers:
            # Get matching candidates from the receiving institution
            receiving_transfers = transfers_in[
                (transfers_in['institution'].str.lower() == to_inst) &
                (transfers_in['transfer_id'].isna()) &
                (transfers_in['asset'] == asset) &
                (abs(transfers_in['timestamp'] - date) <= time_tolerance)
            ]
            
            # Try to match individual transfers
            for out_idx, out_row in group.iterrows():
                if pd.isna(df.at[out_idx, 'transfer_id']):  # Only if still unmatched
                    for _, receive in receiving_transfers.iterrows():
                        if match_transfer_pair(out_row, receive):
                            transfer_id = str(uuid.uuid4())
                            df.at[out_idx, 'transfer_id'] = transfer_id
                            df.at[receive.name, 'transfer_id'] = transfer_id
                            
                            # Store matching info
                            df.at[out_idx, 'matching_institution'] = to_inst
                            df.at[out_idx, 'matching_date'] = receive['timestamp'].strftime('%Y-%m-%d')
                            df.at[receive.name, 'matching_institution'] = from_inst
                            df.at[receive.name, 'matching_date'] = out_row['timestamp'].strftime('%Y-%m-%d')
                            
                            # Transfer cost basis
                            out_quantity = abs(float(out_row['quantity']))
                            if out_quantity > 0:
                                out_cost_basis = abs(float(out_row.get('cost_basis', 0)))
                                out_cost_basis_per_unit = out_cost_basis / out_quantity
                                df.at[receive.name, 'cost_basis'] = out_cost_basis
                                df.at[receive.name, 'cost_basis_per_unit'] = out_cost_basis_per_unit
                            break

    # Handle internal Coinbase ETH-ETH2 transfers
    eth_eth2_transfers_out = transfers_out[
        (transfers_out['asset'].isin(['ETH', 'ETH2'])) &
        (transfers_out['institution'].str.lower() == 'coinbase') &
        (transfers_out['transfer_id'].isna())
    ]
    
    for out_idx, out_row in eth_eth2_transfers_out.iterrows():
        target_asset = 'ETH2' if out_row['asset'] == 'ETH' else 'ETH'
        matching_candidates = transfers_in[
            (transfers_in['institution'].str.lower() == 'coinbase') &
            (transfers_in['transfer_id'].isna()) &
            (transfers_in['asset'] == target_asset)
        ]
        
        if not matching_candidates.empty:
            for _, receive in matching_candidates.iterrows():
                if match_transfer_pair(out_row, receive):
                    transfer_id = str(uuid.uuid4())
                    df.at[out_idx, 'transfer_id'] = transfer_id
                    df.at[receive.name, 'transfer_id'] = transfer_id
                    
                    # Store matching info
                    df.at[out_idx, 'matching_institution'] = 'coinbase'
                    df.at[out_idx, 'matching_date'] = receive['timestamp'].strftime('%Y-%m-%d')
                    df.at[receive.name, 'matching_institution'] = 'coinbase'
                    df.at[receive.name, 'matching_date'] = out_row['timestamp'].strftime('%Y-%m-%d')
                    
                    # Transfer cost basis
                    out_quantity = abs(float(out_row['quantity']))
                    if out_quantity > 0:
                        out_cost_basis = abs(float(out_row.get('cost_basis', 0)))
                        out_cost_basis_per_unit = out_cost_basis / out_quantity
                        df.at[receive.name, 'cost_basis'] = out_cost_basis
                        df.at[receive.name, 'cost_basis_per_unit'] = out_cost_basis_per_unit
                    break

    # For any remaining unmatched transfers, try one final pass with relaxed matching
    remaining_out = df[(df["type"] == "transfer_out") & (df['transfer_id'].isna())]
    remaining_in = df[(df["type"] == "transfer_in") & (df['transfer_id'].isna())]
    
    for out_idx, out_row in remaining_out.iterrows():
        for _, receive in remaining_in.iterrows():
            if match_transfer_pair(out_row, receive):
                transfer_id = str(uuid.uuid4())
                df.at[out_idx, 'transfer_id'] = transfer_id
                df.at[receive.name, 'transfer_id'] = transfer_id
                
                # Store matching info
                df.at[out_idx, 'matching_institution'] = receive['institution']
                df.at[out_idx, 'matching_date'] = receive['timestamp'].strftime('%Y-%m-%d')
                df.at[receive.name, 'matching_institution'] = out_row['institution']
                df.at[receive.name, 'matching_date'] = out_row['timestamp'].strftime('%Y-%m-%d')
                
                # Transfer cost basis
                out_quantity = abs(float(out_row['quantity']))
                if out_quantity > 0:
                    out_cost_basis = abs(float(out_row.get('cost_basis', 0)))
                    out_cost_basis_per_unit = out_cost_basis / out_quantity
                    df.at[receive.name, 'cost_basis'] = out_cost_basis
                    df.at[receive.name, 'cost_basis_per_unit'] = out_cost_basis_per_unit
                break

    # Print final statistics
    matched_pairs = len(df[df['transfer_id'].notna()]) // 2
    unmatched_out = len(df[(df['type'] == 'transfer_out') & (df['transfer_id'].isna())])
    unmatched_in = len(df[(df['type'] == 'transfer_in') & (df['transfer_id'].isna())])
    
    print("\n=== Transfer Reconciliation Complete ===")
    print(f"Matched pairs: {matched_pairs}")
    print(f"Unmatched transfer out: {unmatched_out}")
    print(f"Unmatched transfer in: {unmatched_in}")
    
    return df

