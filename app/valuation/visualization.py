import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta

@st.cache_data(ttl=60)  # Cache expires after 60 seconds
def load_data():
    """
    Load pre-processed data from CSV exports.
    
    Returns:
        Tuple of (transactions, portfolio_time_series, fifo_gains, avg_gains)
    """
    # Load transactions with timestamp parsing
    transactions = pd.read_csv("output/transactions_normalized.csv")
    transactions["timestamp"] = pd.to_datetime(transactions["timestamp"])
    
    # Load portfolio time series with timestamp parsing
    portfolio_ts = pd.read_csv("output/portfolio_timeseries.csv")
    portfolio_ts["timestamp"] = pd.to_datetime(portfolio_ts["timestamp"])
    portfolio_ts.set_index("timestamp", inplace=True)
    
    # Load cost basis data with timestamp parsing
    fifo_gains = pd.read_csv("output/cost_basis_fifo.csv")
    fifo_gains["timestamp"] = pd.to_datetime(fifo_gains["timestamp"])
    
    avg_gains = pd.read_csv("output/cost_basis_avg.csv")
    avg_gains["timestamp"] = pd.to_datetime(avg_gains["timestamp"])
    
    return transactions, portfolio_ts, fifo_gains, avg_gains

def main():
    st.title("Portfolio Analytics Dashboard")
    
    transactions, portfolio_ts, fifo_gains, avg_gains = load_data()
    
    # Sidebar filters
    st.sidebar.header("Filters")
    
    # Date range filter
    min_date = transactions["timestamp"].min().date()
    max_date = transactions["timestamp"].max().date()
    date_range = st.sidebar.date_input(
        "Select Date Range",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date
    )
    
    # Asset filter - ensure all asset names are strings
    assets = transactions["asset"].astype(str).unique()
    selected_asset = st.sidebar.selectbox("Select Asset", options=sorted(assets))
    
    # Apply filters
    filtered_tx = transactions[
        (transactions["timestamp"].dt.date >= date_range[0]) &
        (transactions["timestamp"].dt.date <= date_range[1]) &
        (transactions["asset"].astype(str) == selected_asset)
    ]
    
    filtered_fifo = fifo_gains[
        (fifo_gains["timestamp"].dt.date >= date_range[0]) &
        (fifo_gains["timestamp"].dt.date <= date_range[1]) &
        (fifo_gains["asset"].astype(str) == selected_asset)
    ]
    
    filtered_avg = avg_gains[
        (avg_gains["timestamp"].dt.date >= date_range[0]) &
        (avg_gains["timestamp"].dt.date <= date_range[1]) &
        (avg_gains["asset"].astype(str) == selected_asset)
    ]
    
    # Portfolio Value Chart
    st.header("Portfolio Value Over Time")
    st.line_chart(portfolio_ts["portfolio_value"])
    
    # Cost Basis Analysis
    st.header("Cost Basis Analysis")
    
    # Tabs for different cost basis methods
    tab1, tab2 = st.tabs(["FIFO Method", "Average Cost Method"])
    
    with tab1:
        if not filtered_fifo.empty:
            # FIFO Gains/Losses Chart
            fig_fifo = px.line(
                filtered_fifo,
                x="timestamp",
                y="gain_loss",
                title=f"FIFO Realized Gains/Losses - {selected_asset}",
                labels={"gain_loss": "Gain/Loss ($)", "timestamp": "Date"}
            )
            st.plotly_chart(fig_fifo)
            
            # FIFO Summary
            st.subheader("FIFO Summary")
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric(
                    "Total Realized Gain/Loss",
                    f"${filtered_fifo['gain_loss'].sum():,.2f}"
                )
            with col2:
                st.metric(
                    "Average Holding Period",
                    f"{filtered_fifo['holding_period'].mean():.1f} days"
                )
            with col3:
                st.metric(
                    "Number of Sales",
                    len(filtered_fifo)
                )
            
            # FIFO Detailed Table
            st.subheader("FIFO Transaction Details")
            st.dataframe(filtered_fifo)
        else:
            st.info("No FIFO gains/losses data available for the selected period.")
    
    with tab2:
        if not filtered_avg.empty:
            # Average Cost Gains/Losses Chart
            fig_avg = px.line(
                filtered_avg,
                x="timestamp",
                y="gain_loss",
                title=f"Average Cost Realized Gains/Losses - {selected_asset}",
                labels={"gain_loss": "Gain/Loss ($)", "timestamp": "Date"}
            )
            st.plotly_chart(fig_avg)
            
            # Average Cost Summary
            st.subheader("Average Cost Summary")
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric(
                    "Total Realized Gain/Loss",
                    f"${filtered_avg['gain_loss'].sum():,.2f}"
                )
            with col2:
                st.metric(
                    "Average Holding Period",
                    f"{filtered_avg['holding_period'].mean():.1f} days"
                )
            with col3:
                st.metric(
                    "Number of Sales",
                    len(filtered_avg)
                )
            
            # Average Cost Detailed Table
            st.subheader("Average Cost Transaction Details")
            st.dataframe(filtered_avg)
        else:
            st.info("No average cost gains/losses data available for the selected period.")
    
    # Transaction History
    st.header("Transaction History")
    st.dataframe(filtered_tx)
    
    # Asset Allocation
    st.header("Asset Allocation")
    asset_summary = transactions.groupby("asset")["quantity"].sum().reset_index()
    asset_summary["asset"] = asset_summary["asset"].astype(str)  # Ensure asset names are strings
    fig_allocation = px.bar(
        asset_summary,
        x="asset",
        y="quantity",
        title="Current Asset Holdings"
    )
    st.plotly_chart(fig_allocation)

if __name__ == "__main__":
    main()
