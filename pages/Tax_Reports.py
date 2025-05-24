import streamlit as st
import pandas as pd
from datetime import datetime
from app.analytics.portfolio import calculate_cost_basis_fifo, calculate_cost_basis_avg

def load_data():
    """Load and validate transaction data"""
    try:
        transactions = pd.read_csv("output/transactions_normalized.csv", parse_dates=["timestamp"])
        if transactions.empty:
            st.error("No transaction data found.")
            return None
        return transactions
    except Exception as e:
        st.error(f"Error loading transaction data: {str(e)}")
        return None

def display_tax_report(transactions: pd.DataFrame, year: int, selected_symbol: str):
    """Display tax report for the selected year and asset"""
    st.header(f"Tax Report for {year}")
    
    # Filter transactions by year
    transactions['year'] = transactions['timestamp'].dt.year
    year_transactions = transactions[transactions['year'] == year].copy()
    
    if year_transactions.empty:
        st.warning(f"No transactions found for {year}")
        return
    
    # Filter by selected asset if not "All Assets"
    if selected_symbol != "All Assets":
        year_transactions = year_transactions[year_transactions['asset'] == selected_symbol]
        if year_transactions.empty:
            st.warning(f"No transactions found for {selected_symbol} in {year}")
            return
    
    # Calculate cost basis using FIFO method
    st.subheader("FIFO Cost Basis")
    fifo_basis = calculate_cost_basis_fifo(year_transactions)
    if not fifo_basis.empty:
        st.dataframe(fifo_basis, hide_index=True, use_container_width=True)
        
        # Calculate summary metrics
        total_gain_loss = fifo_basis['gain_loss'].sum()
        total_proceeds = fifo_basis['amount'] * fifo_basis['price']
        total_cost = fifo_basis['amount'] * fifo_basis['cost_basis']
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Proceeds", f"${total_proceeds.sum():,.2f}")
        with col2:
            st.metric("Total Cost Basis", f"${total_cost.sum():,.2f}")
        with col3:
            st.metric("Total Gain/Loss", f"${total_gain_loss:,.2f}")
    else:
        st.info("No FIFO cost basis calculations available")
    
    # Calculate cost basis using Average Cost method
    st.subheader("Average Cost Basis")
    avg_basis = calculate_cost_basis_avg(year_transactions)
    if not avg_basis.empty:
        st.dataframe(avg_basis, hide_index=True, use_container_width=True)
        
        # Calculate summary metrics
        total_cost_basis = avg_basis['avg_cost_basis'].sum()
        total_value = year_transactions['amount'] * year_transactions['price']
        total_gain_loss = total_value.sum() - total_cost_basis
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Value", f"${total_value.sum():,.2f}")
        with col2:
            st.metric("Total Cost Basis", f"${total_cost_basis:,.2f}")
        with col3:
            st.metric("Total Gain/Loss", f"${total_gain_loss:,.2f}")
    else:
        st.info("No average cost basis calculations available")
    
    # Display transaction details
    st.subheader("Transaction Details")
    st.dataframe(year_transactions, hide_index=True, use_container_width=True)

def main():
    st.title("Tax Reports")
    st.write("Generate and view tax reports for your cryptocurrency transactions.")
    
    # Load transaction data
    transactions = load_data()
    if transactions is None:
        return
        
    # Initialize portfolio reporting
    reporter = PortfolioReporting(transactions)
    
    # Year selection - use most recently completed year as default
    current_year = datetime.now().year
    available_years = list(range(current_year - 1, current_year - 6, -1))  # Last 5 completed years
    default_year = current_year - 1  # Most recently completed year (2024)
    
    year = st.selectbox(
        "Select Tax Year",
        available_years,
        index=0  # First year (2024) will be selected by default
    )
    
    # Add option to include transfers in tax report
    include_transfers = st.checkbox("Include Transfers in Tax Report", value=True, 
                                  help="When enabled, transfer_out transactions will be included in tax calculations")
    
    # Ensure the cost_basis column exists in transactions
    if 'cost_basis' not in transactions.columns:
        transactions['cost_basis'] = 0.0
    
    # Get sales transactions for the selected year
    sales_df = reporter.show_sell_transactions_with_lots(include_transfers=include_transfers)
    
    # Ensure the cost_basis column exists in sales_df
    if not sales_df.empty and 'cost_basis' not in sales_df.columns:
        sales_df['cost_basis'] = 0.0
    
    if not sales_df.empty:
        sales_df['date'] = pd.to_datetime(sales_df['date'])
        year_sales = sales_df[sales_df['date'].dt.year == year]
        # Get unique assets from sales transactions for the selected year
        available_assets = ["All Assets"] + sorted(year_sales['asset'].unique().tolist())
    else:
        available_assets = ["All Assets"]
    
    # Add symbol filter
    selected_symbol = st.selectbox(
        "Filter by Asset",
        available_assets,
        index=0  # "All Assets" will be selected by default
    )
    
    # Display tax report with the selected filters
    display_tax_report(transactions, year, selected_symbol)

if __name__ == "__main__":
    main() 