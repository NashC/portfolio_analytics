import streamlit as st
import pandas as pd
from datetime import datetime
from app.analytics.portfolio import compute_portfolio_time_series

def display_transfers(transactions: pd.DataFrame):
    """Display transfer analysis for the portfolio"""
    st.header("Transfer Analysis")
    
    # Filter for transfer transactions
    transfers = transactions[transactions['type'] == 'transfer'].copy()
    
    if transfers.empty:
        st.info("No transfer transactions found")
        return
    
    # Group transfers by date and asset
    transfers['date'] = transfers['timestamp'].dt.date
    transfers_by_date = transfers.groupby(['date', 'asset']).agg({
        'amount': 'sum',
        'price': 'mean',
        'fees': 'sum'
    }).reset_index()
    
    # Calculate transfer value
    transfers_by_date['value'] = transfers_by_date['amount'] * transfers_by_date['price']
    
    # Display transfer summary
    st.subheader("Transfer Summary")
    
    # Calculate summary metrics
    total_transfers = len(transfers)
    total_value = transfers_by_date['value'].sum()
    total_fees = transfers_by_date['fees'].sum()
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Transfers", f"{total_transfers:,}")
    with col2:
        st.metric("Total Value", f"${total_value:,.2f}")
    with col3:
        st.metric("Total Fees", f"${total_fees:,.2f}")
    
    # Display transfers by asset
    st.subheader("Transfers by Asset")
    asset_summary = transfers_by_date.groupby('asset').agg({
        'amount': 'sum',
        'value': 'sum',
        'fees': 'sum'
    }).reset_index()
    
    st.dataframe(asset_summary, hide_index=True, use_container_width=True)
    
    # Display transfer timeline
    st.subheader("Transfer Timeline")
    timeline = transfers_by_date.sort_values('date')
    st.dataframe(timeline, hide_index=True, use_container_width=True)
    
    # Display transfer details
    st.subheader("Transfer Details")
    st.dataframe(transfers, hide_index=True, use_container_width=True)

# Load data and display transfers
try:
    # Load transaction data
    transactions = pd.read_csv("output/transactions_normalized.csv", parse_dates=["timestamp"])
    if transactions.empty:
        st.error("No transaction data found.")
    else:
        # Display transfers page
        display_transfers(transactions)
except Exception as e:
    st.error(f"Error loading transaction data: {str(e)}") 