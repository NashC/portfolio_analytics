# Portfolio Analytics

A Python analytics engine for tracking portfolio performance, cost basis, and tax-relevant metrics across brokerages, crypto exchanges, and wallets. Ingests CSV transaction exports from multiple institutions, normalizes them into a unified ledger, and provides FIFO/average cost basis calculations, tax reporting, and an interactive Streamlit dashboard.

The core challenge is normalization: every exchange uses different column names, transaction types, and fee structures. The ingestion layer maps each source to a common schema so downstream analytics don't need to know where the data came from.

## What it does

- **Multi-source ingestion**: Reads CSV exports from Coinbase, Binance US, Gemini, and generic formats, normalizing them into a single transaction ledger
- **Cost basis tracking**: FIFO and average cost methods with per-lot detail, handling fees, staking rewards (with FMV cost basis), and stablecoin exclusions
- **Tax reporting**: Short-term vs. long-term gain categorization, sales history with cost basis, and CSV export for tax filing
- **Real-time pricing**: CoinGecko integration for current valuations and historical price lookups
- **Dashboard**: Streamlit UI with portfolio value over time, asset allocation, performance metrics, and tax summaries
- **REST API**: FastAPI endpoints for programmatic access to portfolio data

## Quick Start

```bash
git clone https://github.com/NashC/portfolio_analytics.git
cd portfolio_analytics
uv venv && source .venv/bin/activate
uv pip install -e ".[dev]"

# Initialize database and import data
python scripts/migration.py

# Place CSV exports in data/transaction_history/

# Launch dashboard
PYTHONPATH=$(pwd) streamlit run ui/streamlit_app_v2.py --server.port 8502

# Or start the API
uvicorn app.api:app --reload --port 8000
```

## Project Structure

```
app/
├── ingestion/     # CSV loaders and schema normalization
├── valuation/     # Portfolio valuation engine
├── analytics/     # Performance metrics and returns calculations
├── services/      # Business logic layer
├── api/           # FastAPI routers
├── models/        # SQLAlchemy ORM models
└── schemas/       # Pydantic validation schemas
ui/                # Streamlit dashboard (v2 = production)
tests/             # Unit and integration tests with fixtures
docs/              # Architecture, development, and user guides
scripts/           # Migration, analytics, and benchmarking utilities
```

## Testing and CI

```bash
# Run full suite
pytest

# With coverage (80% minimum threshold)
pytest --cov=app --cov-report=html
```

CI runs on GitHub Actions with Poetry: pre-commit hooks (black, isort, ruff, mypy) then the test suite with coverage reporting. Local development uses `uv` for faster dependency resolution.

## Tech Stack

Python 3.9+, FastAPI, Streamlit, SQLAlchemy 2.0, pandas, yfinance, pycoingecko, Plotly, pytest. Packaged with hatchling via `pyproject.toml`.

## License

MIT
