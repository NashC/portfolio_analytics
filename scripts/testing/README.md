# Testing Scripts

This directory contains testing scripts for validating portfolio analytics functionality.

## Scripts

### `test_portfolio_cleaned.py`
Main portfolio calculation testing script:
- Portfolio value calculation validation
- Holdings accuracy verification
- Price data integration testing
- Performance metrics validation

**Usage:**
```bash
python scripts/testing/test_portfolio_cleaned.py
```

**Expected Output:**
- Portfolio value: ~$977K
- Top assets: BTC (~$431K), VOO (~$186K), ETH (~$177K)
- Asset count: 64 assets
- Transaction processing: ~4,081 transactions

## Purpose

This directory contains scripts that:
- Validate core portfolio calculations
- Test data processing pipelines
- Verify expected results
- Ensure system reliability

## Integration with Main Test Suite

These scripts complement the main test suite in `/tests/` by providing:
- End-to-end testing with real data
- Performance validation
- Integration testing
- Manual verification tools

## When to Run

Run these scripts:
- After making changes to portfolio calculation logic
- When debugging unexpected results
- Before deploying changes
- As part of regular health checks

## Expected Results

The scripts should produce consistent, expected results that match the documented portfolio metrics in the project overview. 