# Debug Scripts

This directory contains debugging scripts for troubleshooting issues in the portfolio analytics system.

## Scripts

### `debug_portfolio_issues.py`
Comprehensive debugging script that tests multiple aspects of the portfolio calculation:
- yfinance API integration
- ETH/ETH2 consolidation
- Price data loading
- Portfolio calculation accuracy

**Usage:**
```bash
python scripts/debug/debug_portfolio_issues.py
```

### `debug_holdings_calculation.py`
Focused debugging for holdings calculation issues:
- Transaction filtering
- Cumulative holdings calculation
- Asset consolidation logic

**Usage:**
```bash
python scripts/debug/debug_holdings_calculation.py
```

### `debug_price_data.py`
Price data loading and validation debugging:
- Historical CSV file loading
- External API fallbacks (CoinGecko, yfinance)
- Price data coverage analysis

**Usage:**
```bash
python scripts/debug/debug_price_data.py
```

## When to Use

Run these scripts when you encounter:
- Unexpected portfolio values
- Price data loading errors
- Holdings calculation discrepancies
- yfinance API errors
- Asset consolidation issues

## Expected Output

Each script provides detailed diagnostic information and should help identify the root cause of issues in the portfolio analytics system. 