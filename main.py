import os
import uuid
import pandas as pd
from datetime import datetime
from ingestion import process_transactions
from normalization import normalize_data
from transfers import reconcile_transfers
from analytics import compute_portfolio_time_series_with_external_prices
from reporting import PortfolioReporting

def main():
    data_dir = "data/transaction_history"
    config_path = "config/schema_mapping.yaml"
    output_dir = "output"
    os.makedirs(output_dir, exist_ok=True)

    # Step 1: Ingest transactions from all CSV sources
    print("📥 Ingesting transactions...")
    transactions = process_transactions(data_dir, config_path)
    if transactions.empty:
        print("🚫 No data to process.")
        return

    # Step 2: Reconcile internal transfers
    print("🔁 Reconciling internal transfers...")
    transactions = reconcile_transfers(transactions)

    # Step 3: Add unique transaction_id for downstream tracing
    transactions.insert(0, "transaction_id", [str(uuid.uuid4()) for _ in range(len(transactions))])

    # Step 4: Export full raw data (for audits or debugging)
    raw_export_path = os.path.join(output_dir, "transactions_raw.csv")
    transactions.to_csv(raw_export_path, index=False)
    print(f"✅ Full raw transactions exported to: {raw_export_path}")

    # Step 5: Export normalized data (lean format)
    canonical_columns = [
        "transaction_id", "timestamp", "type", "asset", "quantity", "price", "fees",
        "subtotal", "total", "currency", "source_account", "destination_account", 
        "institution", "transfer_id", "matching_institution", "matching_date"
    ]
    
    # Ensure transfer_id and matching columns are in the transactions DataFrame
    if "transfer_id" not in transactions.columns:
        print("⚠️ Warning: transfer_id column not found in transactions")
        transactions["transfer_id"] = None
    if "matching_institution" not in transactions.columns:
        print("⚠️ Warning: matching_institution column not found in transactions")
        transactions["matching_institution"] = None
    if "matching_date" not in transactions.columns:
        print("⚠️ Warning: matching_date column not found in transactions")
        transactions["matching_date"] = None
    
    normalized_transactions = transactions[canonical_columns].copy()
    
    # Debug print transfer matching statistics
    transfer_out = normalized_transactions[normalized_transactions["type"] == "transfer_out"]
    transfer_in = normalized_transactions[normalized_transactions["type"] == "transfer_in"]
    matched_out = transfer_out[transfer_out["transfer_id"].notna()]
    matched_in = transfer_in[transfer_in["transfer_id"].notna()]
    
    print("\nTransfer matching statistics:")
    print(f"Total transfer out: {len(transfer_out)}")
    print(f"Total transfer in: {len(transfer_in)}")
    print(f"Matched transfer out: {len(matched_out)}")
    print(f"Matched transfer in: {len(matched_in)}")
    
    normalized_export_path = os.path.join(output_dir, "transactions_normalized.csv")
    normalized_transactions.to_csv(normalized_export_path, index=False)
    print(f"✅ Normalized transactions exported to: {normalized_export_path}")

    # Initialize portfolio reporting
    print("📊 Initializing portfolio reporting...")
    reporter = PortfolioReporting(transactions)

    # Step 6: Portfolio value time series
    print("📈 Computing portfolio value time series...")
    portfolio_ts = reporter.calculate_portfolio_value()
    portfolio_ts.to_csv(os.path.join(output_dir, "portfolio_timeseries.csv"))
    print("✅ Portfolio time series exported.")

    # Step 7: Generate tax reports
    print("🧾 Generating tax reports...")
    current_year = datetime.now().year
    for year in range(current_year - 2, current_year + 1):
        tax_lots, summary = reporter.generate_tax_report(year)
        if not tax_lots.empty:
            tax_lots.to_csv(os.path.join(output_dir, f"tax_lots_{year}.csv"), index=False)
            print(f"✅ Tax report for {year} exported:")
            print(f"   - Net proceeds: ${summary['net_proceeds']:,.2f}")
            print(f"   - Total gain/loss: ${summary['total_gain_loss']:,.2f}")
            print(f"   - Short-term gain/loss: ${summary['short_term_gain_loss']:,.2f}")
            print(f"   - Long-term gain/loss: ${summary['long_term_gain_loss']:,.2f}")

    # Step 8: Generate performance reports
    print("\n📊 Generating performance reports...")
    reporter.generate_performance_report()
    print("✅ Performance report exported.")

    print("\n🏁 Pipeline complete.")

if __name__ == "__main__":
    main()
