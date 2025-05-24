import streamlit as st
import pandas as pd
from datetime import datetime, date
from app.analytics.portfolio import (
    compute_portfolio_time_series,
    compute_portfolio_time_series_with_external_prices,
    calculate_cost_basis_fifo,
    calculate_cost_basis_avg
)
from app.services.price_service import PriceService
from app.db.session import get_db
from app.db.base import Asset, PriceData
from pages.Tax_Reports import display_tax_report
from pages.Transfers import display_transfers

@st.cache_data
def load_transactions():
    """Load and cache the portfolio transaction data as a DataFrame"""
    try:
        transactions = pd.read_csv("output/transactions_normalized.csv", parse_dates=["timestamp"])
        if transactions.empty:
            st.error("No transaction data found.")
            return None
        return transactions
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

def get_portfolio_summary(transactions: pd.DataFrame) -> dict:
    """Calculate portfolio summary metrics"""
    # Get latest portfolio value
    portfolio_value = compute_portfolio_time_series_with_external_prices(transactions)
    total_value = portfolio_value['total'].iloc[-1] if not portfolio_value.empty else 0
    
    # Calculate cost basis
    cost_basis = calculate_cost_basis_avg(transactions)
    total_cost_basis = cost_basis['avg_cost_basis'].sum()
    
    # Calculate unrealized P/L
    total_unrealized_pl = total_value - total_cost_basis
    
    return {
        'total_value': total_value,
        'total_cost_basis': total_cost_basis,
        'total_unrealized_pl': total_unrealized_pl
    }

def get_asset_allocation(transactions: pd.DataFrame) -> pd.DataFrame:
    """Calculate current asset allocation"""
    # Get latest portfolio value
    portfolio_value = compute_portfolio_time_series_with_external_prices(transactions)
    if portfolio_value.empty:
        return pd.DataFrame()
    
    # Calculate allocation percentages
    latest_values = portfolio_value.iloc[-1].drop('total')
    total = latest_values.sum()
    allocation = pd.DataFrame({
        'Asset': latest_values.index,
        'Value': latest_values.values,
        'Allocation': (latest_values / total * 100).round(2)
    })
    
    return allocation.sort_values('Value', ascending=False)

def get_recent_transactions(transactions: pd.DataFrame, n: int = 10) -> pd.DataFrame:
    """Get the n most recent transactions"""
    return transactions.sort_values('timestamp', ascending=False).head(n)

def get_all_transactions(transactions: pd.DataFrame) -> pd.DataFrame:
    """Get all transactions with date column"""
    df = transactions.copy()
    df['date'] = df['timestamp'].dt.date
    return df

def main():
    st.set_page_config(
        page_title="Portfolio Analytics",
        page_icon="📈",
        layout="wide"
    )
    
    st.title("Portfolio Analytics")
    
    # Load data
    transactions = load_transactions()
    if transactions is None:
        st.error("Could not initialize portfolio reporting. Please check your data.")
        return
    
    # Initialize price service
    price_service = PriceService()
    
    # Sidebar navigation
    st.sidebar.title("Navigation")
    page = st.sidebar.radio(
        "Select Page",
        ["Overview", "Tax Reports", "Transfers"]
    )
    
    # Year selection in sidebar
    years = sorted(transactions['timestamp'].dt.year.unique(), reverse=True)
    year = st.sidebar.selectbox("Select Year", years, index=0)
    
    # Asset selection in sidebar (robust to mixed types and NaN)
    asset_series = transactions['asset'].dropna().astype(str).str.strip()
    asset_list = sorted([a for a in asset_series.unique() if a])
    assets = ["All Assets"] + asset_list
    selected_symbol = st.sidebar.selectbox("Select Asset", assets, index=0)
    
    if page == "Overview":
        # Display portfolio summary
        st.header("Portfolio Summary")
        summary = get_portfolio_summary(transactions)
        
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
        allocation = get_asset_allocation(transactions)
        st.dataframe(allocation, hide_index=True, use_container_width=True)

        # Debug: Show latest daily holdings
        st.subheader("Debug: Latest Daily Holdings")
        portfolio_value = compute_portfolio_time_series_with_external_prices(transactions)
        st.dataframe(portfolio_value.tail(10))

        # Debug: Show available price data for all assets
        st.subheader("Debug: Price Data for Portfolio Assets")
        if not portfolio_value.empty:
            prices = price_service.get_multi_asset_prices(
                portfolio_value.columns.drop('total'),
                portfolio_value.index.min(),
                portfolio_value.index.max()
            )
            st.dataframe(prices)

        # Display recent transactions
        st.header("Recent Transactions")
        recent_tx = get_recent_transactions(transactions)
        st.dataframe(recent_tx, hide_index=True, use_container_width=True)
        
        # Display all transactions with filters
        st.header("All Transactions")
        all_tx = get_all_transactions(transactions)
        
        # Filter transactions by date range
        date_col1, date_col2 = st.columns(2)
        with date_col1:
            start_date = st.date_input("Start Date", min(all_tx['date']))
        with date_col2:
            end_date = st.date_input("End Date", max(all_tx['date']))
        
        # Filter transactions
        filtered_tx = all_tx[
            (all_tx['date'] >= start_date) &
            (all_tx['date'] <= end_date)
        ]
        
        st.dataframe(filtered_tx)
        
    elif page == "Tax Reports":
        display_tax_report(transactions, year, selected_symbol)
    elif page == "Transfers":
        display_transfers(transactions)

if __name__ == "__main__":
    main()
