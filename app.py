import streamlit as st
import pandas as pd

@st.cache_data
def load_data():
    """
    Load pre-processed data from the output directory.
    """
    try:
        transactions = pd.read_csv("output/transactions_normalized.csv", parse_dates=["timestamp"])
    except Exception as e:
        st.error("Error loading transactions: " + str(e))
        transactions = pd.DataFrame()
        
    try:
        portfolio_ts = pd.read_csv("output/portfolio_timeseries.csv", parse_dates=["timestamp"], index_col="timestamp")
    except Exception as e:
        st.error("Error loading portfolio time series: " + str(e))
        portfolio_ts = pd.DataFrame()
        
    return transactions, portfolio_ts

def main():
    st.title("Portfolio Analytics Dashboard")

    # Load the data
    transactions, portfolio_ts = load_data()

    if transactions.empty:
        st.warning("No transaction data loaded. Please run the ingestion pipeline first.")
        return

    st.header("Portfolio Value Over Time")
    if not portfolio_ts.empty and "portfolio_value" in portfolio_ts.columns:
        st.line_chart(portfolio_ts["portfolio_value"])
    else:
        st.info("Portfolio time series not available.")

    st.header("Transaction Ledger")
    st.dataframe(transactions)

    # Sidebar filters
    st.sidebar.header("Filters")

    # Filter by asset
    assets = transactions["asset"].dropna().unique()
    selected_asset = st.sidebar.selectbox("Select Asset", options=sorted(assets))
    filtered_tx = transactions[transactions["asset"] == selected_asset]

    # Filter by date range
    min_date = transactions["timestamp"].min().date()
    max_date = transactions["timestamp"].max().date()
    date_range = st.sidebar.date_input("Select Date Range", value=(min_date, max_date))
    if isinstance(date_range, tuple) and len(date_range) == 2:
        start_date, end_date = date_range
        filtered_tx = filtered_tx[
            (filtered_tx["timestamp"].dt.date >= start_date) &
            (filtered_tx["timestamp"].dt.date <= end_date)
        ]

    st.subheader(f"Transactions for {selected_asset}")
    st.write(f"Total transactions: {len(filtered_tx)}")
    st.dataframe(filtered_tx)

    # Optional: show additional charts (e.g., asset allocation)
    st.header("Asset Allocation")
    asset_summary = transactions.groupby("asset")["quantity"].sum().reset_index()
    st.bar_chart(asset_summary.set_index("asset"))

if __name__ == "__main__":
    main()
