import os
import pandas as pd
from ingestion import load_schema_config, ingest_csv
from normalization import normalize_data
from analytics import compute_portfolio_time_series, calculate_cost_basis_fifo, calculate_cost_basis_avg
from transfers import reconcile_transfers

def match_file_to_mapping(file_name: str, schema_config: dict):
    for institution, entry in schema_config.items():
        if isinstance(entry, dict) and "file_pattern" in entry:
            if file_name == entry["file_pattern"]:
                return institution, None, entry["mapping"]
        elif isinstance(entry, dict):
            for sub_key, sub_entry in entry.items():
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

def main():
    data_dir = "data"
    config_path = "config/schema_mapping.yaml"
    output_dir = "output"
    os.makedirs(output_dir, exist_ok=True)

    # Process raw CSV files to get the initial transactions DataFrame.
    transactions = process_transactions(data_dir, config_path)
    if transactions.empty:
        print("🚫 No data to export.")
        return

    # Normalize transaction types and other data.
    transactions = normalize_data(transactions)
    
    # 🔥 Force timestamp into datetime format to avoid string arithmetic errors
    transactions["timestamp"] = pd.to_datetime(transactions["timestamp"], errors="coerce")

    # Reconcile transfers to tag paired transfer_in and transfer_out events.
    transactions = reconcile_transfers(transactions)
    
    # Export normalized and reconciled transactions.
    transactions.to_csv(os.path.join(output_dir, "transactions_normalized.csv"), index=False)
    print("✅ Normalized transactions exported.")

    # Optionally, compute and export other analytics.
    portfolio_ts = compute_portfolio_time_series(transactions)
    portfolio_ts.to_csv(os.path.join(output_dir, "portfolio_timeseries.csv"))
    
    fifo_cb = calculate_cost_basis_fifo(transactions)
    fifo_cb.to_csv(os.path.join(output_dir, "cost_basis_fifo.csv"), index=False)
    
    avg_cb = calculate_cost_basis_avg(transactions)
    avg_cb.to_csv(os.path.join(output_dir, "cost_basis_avg.csv"), index=False)

if __name__ == "__main__":
    main()
