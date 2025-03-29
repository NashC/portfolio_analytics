import streamlit as st
import pandas as pd

def load_data():
    """
    Load pre-processed data from CSV exports.
    
    Returns:
        Tuple of (transactions, portfolio_time_series)
    """
    transactions = pd.read_csv("output/transactions_normalized.csv", parse_dates=["timestamp"])
    portfolio_ts = pd.read_csv("output/portfolio_timeseries.csv", parse_dates=["timestamp"], index_col="timestamp")
    return transactions, portfolio_ts

def main():
    st.title("Portfolio Analytics Dashboard")
    
    transactions, portfolio_ts = load_data()
    
    st.header("Portfolio Value Over Time")
    st.line_chart(portfolio_ts["portfolio_value"])
    
    st.header("Transaction Ledger")
    st.dataframe(transactions)
    
    # Filter by asset
    assets = transactions["asset"].unique()
    asset_filter = st.selectbox("Select Asset", options=assets)
    filtered_transactions = transactions[transactions["asset"] == asset_filter]
    
    st.subheader(f"Transactions for {asset_filter}")
    st.dataframe(filtered_transactions)
    
    # Additional visualizations (e.g., realized gains, asset allocation) can be added here.
    
if __name__ == "__main__":
    main()
