import os
import uuid
import pandas as pd
from ingestion import process_transactions
from normalization import normalize_data
from transfers import reconcile_transfers
from analytics import (
    compute_portfolio_time_series_with_external_prices,
    compute_portfolio_time_series,
    calculate_cost_basis_fifo,
    calculate_cost_basis_avg,
)

def main():
    data_dir = "data"
    config_path = "config/schema_mapping.yaml"
    output_dir = "output"
    os.makedirs(output_dir, exist_ok=True)

    # Step 1: Ingest transactions from all CSV sources
    print("📥 Ingesting transactions...")
    transactions = process_transactions(data_dir, config_path)
    if transactions.empty:
        print("🚫 No data to process.")
        return

    # Step 2: Normalize schema and numeric fields
    print("🔧 Normalizing transactions...")
    transactions = normalize_data(transactions)

    # Step 3: Reconcile internal transfers
    print("🔁 Reconciling internal transfers...")
    transactions = reconcile_transfers(transactions)

    # Step 4: Add unique transaction_id for downstream tracing
    transactions.insert(0, "transaction_id", [str(uuid.uuid4()) for _ in range(len(transactions))])

    # Step 5: Export full raw data (for audits or debugging)
    raw_export_path = os.path.join(output_dir, "transactions_raw.csv")
    transactions.to_csv(raw_export_path, index=False)
    print(f"✅ Full raw transactions exported to: {raw_export_path}")

    # Step 6: Export normalized data (lean format)
    canonical_columns = [
        "transaction_id", "timestamp", "type", "asset", "quantity", "price", "fees",
        "currency", "source_account", "destination_account", "user_id", "institution",
        "file_type", "transfer_id", "notes"
    ]
    normalized_transactions = transactions[[col for col in canonical_columns if col in transactions.columns]]
    normalized_export_path = os.path.join(output_dir, "transactions_normalized.csv")
    normalized_transactions.to_csv(normalized_export_path, index=False)
    print(f"✅ Normalized transactions exported to: {normalized_export_path}")

    # Step 7: Portfolio value using external prices (daily valuation)
    print("📈 Computing portfolio value with external prices...")
    portfolio_ts = compute_portfolio_time_series_with_external_prices(transactions)
    portfolio_ts.to_csv(os.path.join(output_dir, "portfolio_timeseries.csv"))
    print("✅ Portfolio time series exported.")

    # Step 8: Cost basis calculations
    print("📊 Calculating FIFO cost basis...")
    fifo_cb = calculate_cost_basis_fifo(transactions)
    fifo_cb.to_csv(os.path.join(output_dir, "cost_basis_fifo.csv"), index=False)
    print("✅ FIFO cost basis exported.")

    print("📊 Calculating average cost basis...")
    avg_cb = calculate_cost_basis_avg(transactions)
    avg_cb.to_csv(os.path.join(output_dir, "cost_basis_avg.csv"), index=False)
    print("✅ Average cost basis exported.")

    print("🏁 Pipeline complete.")

if __name__ == "__main__":
    main()
