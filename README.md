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
- 📊 Enhanced Streamlit dashboard with 5-6x performance improvement
- 📤 Exports normalized data, gains, cost basis, and time series to CSV
- 💾 SQLite database for efficient price data storage and retrieval
- 🔄 Smart asset symbol mapping (e.g., CGLD → CELO, ETH2 → ETH)
- 📊 Historical price tracking with multiple data sources
- 🧾 Comprehensive tax reporting features:
  - FIFO cost basis calculation
  - Staking rewards tracking with FMV cost basis
  - Per-transaction tax lot details
  - Sales history with cost basis and gain/loss
  - Short-term vs long-term gain categorization
  - Tax report CSV export for easy filing
  - Accurate net proceeds calculation with proper fee handling
  - Stablecoin transaction exclusion from tax calculations
  - Detailed transaction breakdown with debug logging
  - Real-time summary metrics from sales history

---

## 📁 Project Structure

```
portfolio_analytics/
│
├── README.md                 # Project documentation
├── pyproject.toml           # Poetry build and dependencies
├── requirements.txt         # Python dependencies
├── pytest.ini              # Test configuration
├── .pre-commit-config.yaml  # Code quality tools
├── .github/workflows/       # CI/CD pipelines
│
├── 📦 app/                  # Core application code
│   ├── main.py             # FastAPI entry point
│   ├── settings.py         # Configuration
│   ├── db/                 # Database models and session
│   ├── models/             # SQLAlchemy models
│   ├── schemas/            # Pydantic schemas
│   ├── api/                # FastAPI routers & REST endpoints
│   ├── services/           # Business logic services
│   ├── ingestion/          # Data loaders and normalization
│   ├── valuation/          # Portfolio valuation engine
│   ├── analytics/          # Performance metrics & returns
│   └── commons/            # Shared utilities
│
├── 🎨 ui/                   # User interface
│   ├── streamlit_app_v2.py # Enhanced dashboard (production)
│   ├── streamlit_app.py    # Legacy dashboard
│   └── components/         # Reusable UI components
│
├── 🗃️ data/                 # Data storage
│   ├── databases/          # Database files (portfolio.db, schema.sql)
│   ├── temp/               # Temporary files
│   ├── exports/            # Generated exports
│   ├── historical_price_data/ # Price data CSVs
│   └── transaction_history/   # Input transaction CSVs
│
├── 🔧 scripts/             # Utility scripts & legacy code
│   ├── migration.py        # Database migration
│   ├── analytics.py        # Legacy analytics
│   ├── ingestion.py        # Legacy ingestion
│   └── benchmark_*.py      # Performance benchmarking
│
├── 📚 docs/                # Documentation hub
│   ├── architecture/       # Technical documentation
│   ├── development/        # Development guides
│   ├── project-management/ # Project status & roadmaps
│   └── user-guides/        # User documentation
│
├── 🧪 tests/               # Test suite
│   ├── unit/              # Unit tests
│   ├── integration/       # Integration tests
│   ├── fixtures/          # Test data
│   └── test_portfolio_*.py # Portfolio-specific tests
│
├── 📓 notebooks/           # Jupyter notebooks
├── ⚙️ config/              # Configuration files
├── 📋 project/             # Project management files
└── output/                 # Generated reports and exports
```

---

## 🛠️ Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/yourusername/portfolio-analytics.git
   cd portfolio-analytics
   ```

2. **Create virtual environment:**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Initialize the database:**
   ```bash
   python scripts/migration.py
   ```

---

## 📥 Input Files

Place your CSV transaction exports inside the `data/transaction_history/` directory.

Expected file names:
- `binanceus_transaction_history.csv`
- `coinbase_transaction_history.csv`
- `gemini_staking_transaction_history.csv`
- `gemini_transaction_history.csv`

Historical price data should be placed in `data/historical_price_data/` with the following format:
- `historical_price_data_daily_[source]_[symbol]USD.csv`

---

## ▶️ Run the App

### 1. Initialize database and import data:
```bash
python scripts/migration.py
```

### 2. Launch Enhanced Dashboard (Recommended):
```bash
# From project root with PYTHONPATH
PYTHONPATH=$(pwd) streamlit run ui/streamlit_app_v2.py --server.port 8502
```

### 3. Alternative: Launch Legacy Dashboard:
```bash
streamlit run ui/streamlit_app.py
```

### 4. Start API Server (Optional):
```bash
uvicorn app.api:app --reload --port 8000
```

---

## 📤 Outputs

Results will be saved to the `output/` directory:
- `transactions_normalized.csv` - Unified transaction ledger
- `portfolio_timeseries.csv` - Portfolio value over time
- `cost_basis_fifo.csv` - FIFO cost basis calculations
- `cost_basis_avg.csv` - Average cost basis calculations
- `performance_report.csv` - Portfolio performance metrics

Database files are stored in `data/databases/`:
- `portfolio.db` - Main SQLite database
- `schema.sql` - Database schema definition

---

## 🧪 Testing

Run the full test suite:
```bash
python -m pytest tests/ -v
```

Run portfolio-specific tests:
```bash
python tests/test_portfolio_simple.py
python tests/test_portfolio_returns_with_real_data.py
```

Performance benchmarking:
```bash
python scripts/simple_benchmark.py
python scripts/demo_dashboard.py
```

---

## 📚 Documentation

Comprehensive documentation is available in the [`docs/`](docs/) directory:

- **[Documentation Hub](docs/README.md)** - Complete documentation index
- **[Development Guide](docs/development/)** - Setup and development workflows
- **[Project Status](docs/project-management/)** - Current status and roadmaps
- **[Performance Metrics](docs/project-management/PERFORMANCE_SUMMARY.md)** - System performance data

---

## 🔭 Roadmap

### ✅ Completed (v2.0)
- [x] Enhanced dashboard with 5-6x performance improvement
- [x] Real-time historical price lookups via CoinGecko
- [x] Tax report summary (short-term vs long-term gains)
- [x] Staking rewards tax lot tracking
- [x] Detailed sales history with cost basis
- [x] REST API endpoints for portfolio data
- [x] Comprehensive test suite (93.4% pass rate)

### 🚧 In Progress
- [ ] Transfer reconciliation engine
- [ ] Multi-currency support
- [ ] API importers (Coinbase, Robinhood, Gemini)

### 🔮 Future
- [ ] Benchmarking against indexes (e.g., S&P 500)
- [ ] User-defined tagging and notes
- [ ] Price data validation and error handling
- [ ] Automated price data updates
- [ ] Multi-user support and team workspaces

---

## 🎯 Project Status

**Version**: 2.0 | **Status**: ✅ Production Ready | **Performance**: 🟢 Excellent

- **Test Coverage**: 85/91 tests passing (93.4%)
- **Performance**: Sub-100ms load times for most operations
- **Data Processing**: 3,795+ transactions across 36 assets
- **Dashboard**: Professional UI with real-time performance monitoring

---

## 👨‍💻 Author

**Nash Collins**

---

## 📝 License

MIT License