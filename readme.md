# 💼 Portfolio Analytics & Tax Tracker

This is a Python-based financial analytics application for tracking portfolio performance, holdings, and tax-relevant metrics across multiple financial institutions — including traditional brokerages, crypto exchanges, and wallets.

Built with `pandas`, `Streamlit`, and modular Python components.

---

## 🚀 Features

- ✅ Ingests transaction history from multiple sources (CSV)
- 🔄 Normalizes different schemas into a unified ledger
- 🔍 Tracks asset-level holdings and portfolio value over time
- 📈 Computes realized gains/losses (FIFO & Average Cost)
- 🔒 Handles internal transfers between accounts
- 📊 Streamlit dashboard for interactive visualization
- 📤 Exports normalized data, gains, cost basis, and time series to CSV

---

## 📁 Project Structure

```
portfolio_app/
├── config/                 # Schema mapping for each institution
├── data/                   # Raw CSV input files (not tracked)
├── output/                 # Auto-generated analytics + exports
├── ingestion.py            # Ingest and normalize raw transactions
├── normalization.py        # Transaction type mapping, currency standardization, etc.
├── analytics.py            # Cost basis, gains/losses, time series tracking
├── visualization.py        # Streamlit dashboard
├── main.py                 # Runs ingestion + export pipeline
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

---

## ▶️ Run the App

### Normalize + process data:
```bash
python main.py
```

### Launch Streamlit dashboard:
```bash
streamlit run visualization.py
```

---

## 📤 Outputs

Results will be saved to the `output/` directory:
- `transactions_normalized.csv`
- `portfolio_timeseries.csv`
- `cost_basis_fifo.csv`
- `cost_basis_avg.csv`

---

## 🧪 Testing

Run unit tests with:

```bash
pytest tests/
```

---

## 🔭 Roadmap

- [ ] Transfer reconciliation engine
- [ ] Multi-currency support
- [ ] Real-time historical price lookups via CoinGecko or CCXT
- [ ] Tax report summary (short-term vs long-term gains)
- [ ] Benchmarking against indexes (e.g., S&P 500)
- [ ] User-defined tagging and notes
- [ ] API importers (e.g., Coinbase, Robinhood, Gemini)

---

## 👨‍💻 Author

**Nash Collins**

---

## 📝 License

MIT License
