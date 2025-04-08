import streamlit as st
import pandas as pd
from datetime import datetime, date
from reporting import PortfolioReporting
from pages.Tax_Reports import display_tax_report
from pages.Transfers import display_transfers

@st.cache_data
def load_data():
    """Load and cache the portfolio data"""
    try:
        # Load transaction data
        transactions = pd.read_csv("output/transactions_normalized.csv", parse_dates=["timestamp"])
        if transactions.empty:
            st.error("No transaction data found.")
            return None
        
        # Initialize portfolio reporting with transactions
        reporter = PortfolioReporting(transactions)
        return reporter
    except Exception as e:
        st.error(f"Error loading transaction data: {str(e)}")
        return None

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
    st.set_page_config(
        page_title="Portfolio Analytics",
        page_icon="📈",
        layout="wide"
    )
    
    st.title("Portfolio Analytics")
    
    # Load data
    reporter = load_data()
    
    if reporter is None:
        st.error("Could not initialize portfolio reporting. Please check your data.")
        return
    
    # Sidebar navigation
    st.sidebar.title("Navigation")
    page = st.sidebar.radio(
        "Select Page",
        ["Overview", "Tax Reports", "Transfers"]
    )
    
    # Year selection in sidebar
    years = sorted(reporter.get_all_transactions()['date'].dt.year.unique(), reverse=True)
    year = st.sidebar.selectbox("Select Year", years, index=0)
    
    # Asset selection in sidebar
    assets = ["All Assets"] + sorted(reporter.get_all_transactions()['asset'].unique().tolist())
    selected_symbol = st.sidebar.selectbox("Select Asset", assets, index=0)
    
    if page == "Overview":
        # Display portfolio summary
        st.header("Portfolio Summary")
        summary = reporter.get_portfolio_summary()
        
        # Display summary metrics
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Value", f"${summary['total_value']:,.2f}")
        with col2:
            st.metric("Total Cost Basis", f"${summary['total_cost_basis']:,.2f}")
        with col3:
            st.metric("Total Unrealized P/L", f"${summary['total_unrealized_pl']:,.2f}")
        
        # Display asset allocation
        st.header("Asset Allocation")
        allocation = reporter.get_asset_allocation()
        st.dataframe(allocation, hide_index=True, use_container_width=True)
        
        # Display recent transactions
        st.header("Recent Transactions")
        recent_tx = reporter.get_recent_transactions()
        st.dataframe(recent_tx, hide_index=True, use_container_width=True)
        
        # Display all transactions with filters
        st.header("All Transactions")
        all_tx = reporter.get_all_transactions()
        
        # Filter transactions by date range
        date_col1, date_col2 = st.columns(2)
        with date_col1:
            start_date = st.date_input("Start Date", min(all_tx['date']))
        with date_col2:
            end_date = st.date_input("End Date", max(all_tx['date']))
        
        # Filter transactions
        filtered_tx = all_tx[
            (all_tx['date'].dt.date >= start_date) &
            (all_tx['date'].dt.date <= end_date)
        ]
        
        st.dataframe(filtered_tx)
        
    elif page == "Tax Reports":
        display_tax_report(reporter, year, selected_symbol)
    elif page == "Transfers":
        display_transfers(reporter)

if __name__ == "__main__":
    main()
