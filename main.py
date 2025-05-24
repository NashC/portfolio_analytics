import os
import uuid
import pandas as pd
from datetime import datetime
from app.ingestion import process_transactions
from app.normalization import normalize_data
from app.transfers import reconcile_transfers
from app.analytics.portfolio import (
    compute_portfolio_time_series,
    compute_portfolio_time_series_with_external_prices,
    calculate_cost_basis_fifo,
    calculate_cost_basis_avg
)
from app.services.price_service import PriceService
from app.db.session import get_db
from app.db.base import Asset, PriceData

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
        "transaction_id", "timestamp", "type", "asset", "amount", "price", "fees",
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

    # Initialize price service
    print("📊 Initializing price service...")
    price_service = PriceService()

    # Step 6: Portfolio value time series
    print("📈 Computing portfolio value time series...")
    portfolio_ts = compute_portfolio_time_series_with_external_prices(normalized_transactions)
    portfolio_ts.to_csv(os.path.join(output_dir, "portfolio_timeseries.csv"))
    print("✅ Portfolio time series exported.")

    # Step 7: Generate tax reports
    print("🧾 Generating tax reports...")
    current_year = datetime.now().year
    for year in range(current_year - 2, current_year + 1):
        # Filter transactions for the year
        year_transactions = normalized_transactions[
            normalized_transactions['timestamp'].dt.year == year
        ]
        
        if not year_transactions.empty:
            # Calculate FIFO cost basis
            fifo_basis = calculate_cost_basis_fifo(year_transactions)
            if not fifo_basis.empty:
                fifo_basis.to_csv(os.path.join(output_dir, f"tax_lots_fifo_{year}.csv"), index=False)
                print(f"✅ FIFO tax report for {year} exported:")
                print(f"   - Total proceeds: ${fifo_basis['amount'] * fifo_basis['price']:,.2f}")
                print(f"   - Total cost basis: ${fifo_basis['amount'] * fifo_basis['cost_basis']:,.2f}")
                print(f"   - Total gain/loss: ${fifo_basis['gain_loss'].sum():,.2f}")
            
            # Calculate average cost basis
            avg_basis = calculate_cost_basis_avg(year_transactions)
            if not avg_basis.empty:
                avg_basis.to_csv(os.path.join(output_dir, f"tax_lots_avg_{year}.csv"), index=False)
                print(f"✅ Average cost tax report for {year} exported:")
                print(f"   - Total cost basis: ${avg_basis['avg_cost_basis'].sum():,.2f}")

    # Step 8: Generate performance reports
    print("\n📊 Generating performance reports...")
    # Calculate performance metrics
    returns = portfolio_ts.pct_change().dropna()
    volatility = returns.std() * (252 ** 0.5) * 100  # Annualized volatility
    sharpe_ratio = (returns.mean() * 252) / (returns.std() * (252 ** 0.5))
    max_drawdown = ((portfolio_ts / portfolio_ts.expanding().max() - 1) * 100).min()
    
    performance_metrics = pd.DataFrame({
        'Metric': ['Total Return', 'Volatility', 'Sharpe Ratio', 'Max Drawdown'],
        'Value': [
            f"{((portfolio_ts.iloc[-1] / portfolio_ts.iloc[0] - 1) * 100):.2f}%",
            f"{volatility:.2f}%",
            f"{sharpe_ratio:.2f}",
            f"{max_drawdown:.2f}%"
        ]
    })
    
    performance_metrics.to_csv(os.path.join(output_dir, "performance_metrics.csv"), index=False)
    print("✅ Performance report exported.")

    print("\n🏁 Pipeline complete.")

if __name__ == "__main__":
    main()
