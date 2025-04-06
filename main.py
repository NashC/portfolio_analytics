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
        "subtotal", "total", "currency", "source_account", "destination_account", 
        "user_id", "institution", "file_type", "transfer_id", "notes"
    ]
    normalized_transactions = transactions[[col for col in canonical_columns if col in transactions.columns]]
    normalized_export_path = os.path.join(output_dir, "transactions_normalized.csv")
    normalized_transactions.to_csv(normalized_export_path, index=False)
    print(f"✅ Normalized transactions exported to: {normalized_export_path}")

    # Initialize portfolio reporting
    print("📊 Initializing portfolio reporting...")
    reporter = PortfolioReporting(transactions)

    # Step 7: Portfolio value time series
    print("📈 Computing portfolio value time series...")
    portfolio_ts = reporter.calculate_portfolio_value()
    portfolio_ts.to_csv(os.path.join(output_dir, "portfolio_timeseries.csv"))
    print("✅ Portfolio time series exported.")

    # Step 8: Generate tax reports
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

    # Step 9: Generate performance reports
    print("\n📊 Generating performance reports...")
    for period in ["YTD", "1Y", "3Y", "5Y"]:
        report = reporter.generate_performance_report(period)
        print(f"\n{period} Performance Summary:")
        print(f"   - Total Return: {report['metrics']['total_return']:.2f}%")
        print(f"   - Annualized Return: {report['metrics']['annualized_return']:.2f}%")
        print(f"   - Volatility: {report['metrics']['volatility']:.2f}%")
        print(f"   - Sharpe Ratio: {report['metrics']['sharpe_ratio']:.2f}")
        print(f"   - Max Drawdown: {report['metrics']['max_drawdown']:.2f}%")
        
        # Export full report
        report_path = os.path.join(output_dir, f"performance_report_{period}.csv")
        pd.DataFrame([report]).to_csv(report_path, index=False)
        print(f"✅ {period} performance report exported.")

    print("\n🏁 Pipeline complete.")

if __name__ == "__main__":
    main()
