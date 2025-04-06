import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, date
from reporting import PortfolioReporting
from menu import render_navigation

# Must be the first Streamlit command
st.set_page_config(
    page_title="Portfolio Analytics",
    page_icon="📊",
    layout="wide"
)

# Render navigation
render_navigation()

def format_date(timestamp):
    """Convert timestamp to YYYY-MM-DD format"""
    return pd.to_datetime(timestamp).strftime('%Y-%m-%d')

@st.cache_data
def load_data():
    """Load pre-processed data from the output directory."""
    try:
        transactions = pd.read_csv("output/transactions_normalized.csv", parse_dates=["timestamp"])
        portfolio_ts = pd.read_csv("output/portfolio_timeseries.csv", parse_dates=["date"], index_col="date")
        return transactions, portfolio_ts
    except Exception as e:
        st.error(f"Error loading data: {str(e)}")
        return pd.DataFrame(), pd.DataFrame()

def display_performance_metrics(metrics: dict):
    """Display performance metrics in a grid layout"""
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Total Return", f"{metrics['total_return']*100:.2f}%")
        st.metric("Annualized Return", f"{metrics['annualized_return']*100:.2f}%")
    
    with col2:
        st.metric("Volatility", f"{metrics['volatility']*100:.2f}%")
        st.metric("Sharpe Ratio", f"{metrics['sharpe_ratio']:.2f}")
    
    with col3:
        st.metric("Max Drawdown", f"{metrics['max_drawdown']*100:.2f}%")

def main():
    st.title("Portfolio Analytics Dashboard")
    
    # Add a brief description
    st.write("This app provides insights into your cryptocurrency portfolio, including performance metrics, asset allocation, and transaction history.")
    
    # Load the data
    transactions, portfolio_ts = load_data()
    
    if transactions.empty or portfolio_ts.empty:
        st.warning("No data available. Please run the data processing pipeline first.")
        return
        
    # Initialize portfolio reporting
    reporter = PortfolioReporting(transactions)
    
    # Display portfolio overview
    st.header("Portfolio Overview")
    
    # Portfolio value chart
    if not portfolio_ts.empty and 'portfolio_value' in portfolio_ts.columns:
        fig = px.line(
            portfolio_ts,
            y='portfolio_value',
            title='Portfolio Value Over Time',
            labels={'portfolio_value': 'Value (USD)', 'date': 'Date'}
        )
        st.plotly_chart(fig, use_container_width=True)
    
    # Asset allocation
    st.header("Asset Allocation")
    latest_holdings = reporter._calculate_daily_holdings().iloc[-1]
    latest_holdings = latest_holdings[latest_holdings != 0]  # Filter out zero holdings
    
    if not latest_holdings.empty:
        fig = px.pie(
            values=latest_holdings.values,
            names=latest_holdings.index,
            title='Current Asset Allocation'
        )
        st.plotly_chart(fig, use_container_width=True)
    
    # Recent transactions
    st.header("Recent Transactions")
    recent_tx = transactions.sort_values('timestamp', ascending=False).head(10)
    if not recent_tx.empty:
        st.dataframe(
            recent_tx[['timestamp', 'type', 'asset', 'quantity', 'price', 'total']],
            hide_index=True
        )
    
    # Performance metrics
    st.header("Performance Metrics")
    try:
        ytd_report = reporter.generate_performance_report("YTD")
        display_performance_metrics(ytd_report['metrics'])
    except Exception as e:
        st.error(f"Error calculating performance metrics: {str(e)}")

if __name__ == "__main__":
    main() 