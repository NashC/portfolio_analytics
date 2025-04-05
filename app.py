import streamlit as st
import pandas as pd
from datetime import datetime, date
from reporting import PortfolioReporting

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
        portfolio_ts = pd.read_csv("output/portfolio_timeseries.csv", parse_dates=["date"], index_col="date")
    except Exception as e:
        st.error("Error loading portfolio time series: " + str(e))
        portfolio_ts = pd.DataFrame()
        
    return transactions, portfolio_ts

def display_performance_metrics(metrics: dict):
    """Display performance metrics in a grid layout"""
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Total Return", f"{metrics['total_return']:.2f}%")
        st.metric("Annualized Return", f"{metrics['annualized_return']:.2f}%")
    
    with col2:
        st.metric("Volatility", f"{metrics['volatility']:.2f}%")
        st.metric("Sharpe Ratio", f"{metrics['sharpe_ratio']:.2f}")
    
    with col3:
        st.metric("Max Drawdown", f"{metrics['max_drawdown']:.2f}%")
        st.metric("Best Day", f"{metrics['best_day']:.2f}%")
        st.metric("Worst Day", f"{metrics['worst_day']:.2f}%")

def main():
    st.set_page_config(page_title="Portfolio Analytics", layout="wide")
    st.title("Portfolio Analytics Dashboard")

    # Load the data
    transactions, portfolio_ts = load_data()

    if transactions.empty:
        st.warning("No transaction data loaded. Please run the ingestion pipeline first.")
        return

    # Initialize portfolio reporting
    reporter = PortfolioReporting(transactions)

    # Sidebar filters
    st.sidebar.header("Filters")
    
    # Time period selection
    period = st.sidebar.selectbox(
        "Select Time Period",
        options=["YTD", "1Y", "3Y", "5Y", "All Time"],
        index=0
    )

    # Asset selection
    assets = transactions["asset"].dropna().unique()
    selected_asset = st.sidebar.selectbox("Select Asset", options=sorted(assets))

    # Main content area
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.header("Portfolio Value Over Time")
        if not portfolio_ts.empty and "portfolio_value" in portfolio_ts.columns:
            # Convert index to datetime if it's not already
            if not isinstance(portfolio_ts.index, pd.DatetimeIndex):
                portfolio_ts.index = pd.to_datetime(portfolio_ts.index)
            st.line_chart(portfolio_ts["portfolio_value"])
        else:
            st.info("Portfolio time series not available.")

    with col2:
        st.header("Current Asset Allocation")
        try:
            portfolio_value = reporter.calculate_portfolio_value()
            if not portfolio_value.empty:
                latest_values = {col.replace("_value", ""): val 
                                for col, val in portfolio_value.iloc[-1].items()
                                if col != "portfolio_value"}
                total_value = sum(latest_values.values())
                
                if total_value > 0:
                    allocation = {asset: (value / total_value * 100) 
                                 for asset, value in latest_values.items()}
                    st.bar_chart(pd.Series(allocation))
                else:
                    st.info("No portfolio value data available.")
            else:
                st.warning("Unable to calculate portfolio value. Check if price data is available.")
        except Exception as e:
            st.error(f"Error calculating portfolio value: {str(e)}")

    # Performance Metrics
    st.header("Performance Metrics")
    try:
        report = reporter.generate_performance_report(period)
        display_performance_metrics(report['metrics'])
    except Exception as e:
        st.error(f"Error generating performance report: {str(e)}")

    # Tax Reports
    st.header("Tax Reports")
    current_year = datetime.now().year
    tax_year = st.selectbox("Select Tax Year", 
                           options=range(current_year - 2, current_year + 1),
                           index=2)
    
    try:
        tax_lots, summary = reporter.generate_tax_report(tax_year)
        if not tax_lots.empty:
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total Proceeds", f"${summary['total_proceeds']:,.2f}")
            with col2:
                st.metric("Total Gain/Loss", f"${summary['total_gain_loss']:,.2f}")
            with col3:
                st.metric("Short-term G/L", f"${summary['short_term_gain_loss']:,.2f}")
            with col4:
                st.metric("Long-term G/L", f"${summary['long_term_gain_loss']:,.2f}")
            
            st.subheader("Tax Lots")
            st.dataframe(tax_lots)
        else:
            st.info(f"No tax lots found for {tax_year}")
    except Exception as e:
        st.error(f"Error generating tax report: {str(e)}")

    # Transaction History
    st.header("Transaction History")
    filtered_tx = transactions[transactions["asset"] == selected_asset]
    
    # Date range filter
    min_date = transactions["timestamp"].min().date()
    max_date = transactions["timestamp"].max().date()
    date_range = st.date_input("Select Date Range", value=(min_date, max_date))
    if isinstance(date_range, tuple) and len(date_range) == 2:
        start_date, end_date = date_range
        filtered_tx = filtered_tx[
            (filtered_tx["timestamp"].dt.date >= start_date) &
            (filtered_tx["timestamp"].dt.date <= end_date)
        ]

    st.write(f"Total transactions: {len(filtered_tx)}")
    st.dataframe(filtered_tx)

if __name__ == "__main__":
    main()
