# 💼 Portfolio Analytics & Tax Tracker

This is a Python-based financial analytics application for tracking portfolio performance, holdings, and tax-relevant metrics across multiple financial institutions — including traditional brokerages, crypto exchanges, and wallets.

Built with `pandas`, `Streamlit`, `SQLAlchemy`, and modular Python components.

---

## 🚀 Features

- ✅ Ingests transaction history from multiple sources (CSV)
- 🔄 Normalizes different schemas into a unified ledger
- 🔍 Tracks asset-level holdings and portfolio value over time
- 📈 Computes realized gains/losses (FIFO & Average Cost)
- 🔒 Handles internal transfers between accounts
- 📊 Streamlit dashboard for interactive visualization
- 📤 Exports normalized data, gains, cost basis, and time series to CSV
- 💾 SQLite database for efficient price data storage and retrieval
- 🔄 Smart asset symbol mapping (e.g., CGLD → CELO, ETH2 → ETH)
- 📊 Historical price tracking with multiple data sources

---

## 📁 Project Structure

```
portfolio_app/
├── config/                 # Schema mapping for each institution
├── data/                   # Raw CSV input files and price data
│   └── historical_price_data/  # Historical price data files
├── output/                 # Auto-generated analytics + exports
├── ingestion.py            # Ingest and normalize raw transactions
├── normalization.py        # Transaction type mapping, currency standardization, etc.
├── analytics.py            # Cost basis, gains/losses, time series tracking
├── visualization.py        # Streamlit dashboard
├── app.py                  # Main Streamlit application
├── database.py            # Database connection and utilities
├── db.py                  # Database models and schemas
├── migration.py           # Database migration and data import
├── price_service.py       # Price data retrieval and management
├── reporting.py           # Portfolio reporting and analysis
├── schema.sql             # Database schema definitions
├── main.py                # Runs ingestion + export pipeline
├── requirements.txt
├── setup.sh
├── .gitignore
└── README.md
```

---

## 🛠️ Setup

Make sure you have **Python 3.10+** installed (3.11 recommended).

```bash
# Clone the repo
git clone https://github.com/yourusername/portfolio-analytics.git
cd portfolio-analytics

# Run setup script (creates virtualenv + installs dependencies)
./setup.sh
```

---

## 📥 Input Files

Place your CSV transaction exports inside the `data/` directory.

Expected file names:
- `binanceus_transaction_history.csv`
- `coinbase_transaction_history.csv`
- `gemini_staking_transaction_history.csv`
- `gemini_transaction_history.csv`

Make sure they match the format defined in `config/schema_mapping.yaml`.

Historical price data should be placed in `data/historical_price_data/` with the following format:
- `historical_price_data_daily_[source]_[symbol]USD.csv`

---

## ▶️ Run the App

### Initialize database and import price data:
```bash
python migration.py
```

### Normalize + process data:
```bash
python main.py
```

### Launch Streamlit dashboard:
```bash
streamlit run app.py
```

---

## 📤 Outputs

Results will be saved to the `output/` directory:
- `transactions_normalized.csv`
- `portfolio_timeseries.csv`
- `cost_basis_fifo.csv`
- `cost_basis_avg.csv`
- `performance_report.csv`

---

## 🧪 Testing

Run unit tests with:

```bash
pytest tests/
```

---

## 🔭 Roadmap

- [x] Real-time historical price lookups via CoinGecko
- [x] Tax report summary (short-term vs long-term gains)
- [ ] Transfer reconciliation engine
- [ ] Multi-currency support
- [ ] Benchmarking against indexes (e.g., S&P 500)
- [ ] User-defined tagging and notes
- [ ] API importers (e.g., Coinbase, Robinhood, Gemini)
- [ ] Price data validation and error handling
- [ ] Automated price data updates

---

## 👨‍💻 Author

**Nash Collins**

---

## 📝 License

MIT License 