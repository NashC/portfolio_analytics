import streamlit as st
import pandas as pd
from datetime import datetime
from reporting import PortfolioReporting
from utils import format_currency, format_number

# Must be the first Streamlit command after imports
st.set_page_config(
    page_title="Transfers",
    page_icon="🔄",
    layout="wide",
    initial_sidebar_state="collapsed",
    menu_items={
        'Get Help': None,
        'Report a bug': None,
        'About': "# Portfolio Analytics\nA tool for analyzing cryptocurrency portfolio performance and generating tax reports."
    }
)

def display_transfers(reporter: PortfolioReporting):
    """Display transfers page with send and receive transactions"""
    st.title("Transfers")
    
    # Get all transfer transactions
    transfers_df = reporter.get_transfer_transactions()
    
    if transfers_df.empty:
        st.info("No transfer transactions found")
        return
    
    # Convert date to datetime for filtering
    transfers_df['date'] = pd.to_datetime(transfers_df['date'])
    
    # Get unique years for filtering
    years = sorted(transfers_df['date'].dt.year.unique(), reverse=True)
    selected_year = st.selectbox("Select Year", years, index=0)
    
    # Get unique assets for filtering
    assets = ["All Assets"] + sorted(transfers_df['asset'].unique().tolist())
    selected_asset = st.selectbox("Select Asset", assets, index=0)
    
    # Filter transfers for selected year and asset
    year_transfers = transfers_df[transfers_df['date'].dt.year == selected_year]
    
    if selected_asset != "All Assets":
        year_transfers = year_transfers[year_transfers['asset'] == selected_asset]
    
    if year_transfers.empty:
        st.info(f"No transfers found for {selected_asset} in {selected_year}")
        return
    
    # Convert date back to string format (YYYY-MM-DD)
    year_transfers['date'] = year_transfers['date'].dt.strftime("%Y-%m-%d")
    
    # Split into send and receive transfers
    send_transfers = year_transfers[year_transfers['type'] == 'transfer_out']
    receive_transfers = year_transfers[year_transfers['type'] == 'transfer_in']
    
    # Display Send Transfers
    st.subheader("Send Transfers")
    if not send_transfers.empty:
        # Calculate cost basis per unit
        send_display_df = send_transfers.copy()
        send_display_df['cost_basis_per_unit'] = send_display_df.apply(
            lambda row: row['cost_basis'] / row['quantity'] if row['quantity'] != 0 else 0,
            axis=1
        )
        
        # Rename columns for display
        send_display_names = {
            'date': 'Date',
            'asset': 'Asset',
            'quantity': 'Quantity',
            'price': 'Price',
            'subtotal': 'Subtotal',
            'fees': 'Fees',
            'cost_basis': 'Cost Basis',
            'cost_basis_per_unit': 'Cost/Unit',
            'net_proceeds': 'Net Proceeds',
            'source_exchange': 'Source',
            'destination_exchange': 'Destination'
        }
        
        # Select only the columns we want to display
        display_columns = ['date', 'asset', 'quantity', 'price', 'subtotal', 'fees', 'cost_basis', 'cost_basis_per_unit', 'net_proceeds', 'source_exchange', 'destination_exchange']
        send_display_df = send_display_df[display_columns].copy()
        
        send_display_df.columns = [send_display_names[col] for col in send_display_df.columns]
        
        # Format dollar columns
        dollar_columns = ['Price', 'Subtotal', 'Fees', 'Cost Basis', 'Cost/Unit', 'Net Proceeds']
        for col in dollar_columns:
            send_display_df[col] = send_display_df[col].apply(lambda x: f"${x:,.2f}")
        
        st.dataframe(send_display_df, hide_index=True, use_container_width=True)
        
        # Download send transfers CSV
        send_csv = send_transfers.to_csv(index=False)
        st.download_button(
            label="Download Send Transfers (CSV)",
            data=send_csv,
            file_name=f"send_transfers_{selected_year}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv"
        )
    else:
        st.info("No send transfers found")
    
    # Display Receive Transfers
    st.subheader("Receive Transfers")
    if not receive_transfers.empty:
        # Calculate cost basis per unit
        receive_display_df = receive_transfers.copy()
        receive_display_df['cost_basis_per_unit'] = receive_display_df.apply(
            lambda row: row['cost_basis'] / row['quantity'] if row['quantity'] != 0 else 0,
            axis=1
        )
        
        # Rename columns for display
        receive_display_names = {
            'date': 'Date',
            'asset': 'Asset',
            'quantity': 'Quantity',
            'price': 'Price',
            'subtotal': 'Subtotal',
            'fees': 'Fees',
            'cost_basis': 'Cost Basis',
            'cost_basis_per_unit': 'Cost/Unit',
            'source_exchange': 'Source',
            'destination_exchange': 'Destination'
        }
        
        # Select only the columns we want to display
        display_columns = ['date', 'asset', 'quantity', 'price', 'subtotal', 'fees', 'cost_basis', 'cost_basis_per_unit', 'source_exchange', 'destination_exchange']
        receive_display_df = receive_display_df[display_columns].copy()
        
        receive_display_df.columns = [receive_display_names[col] for col in receive_display_df.columns]
        
        # Format dollar columns
        dollar_columns = ['Price', 'Subtotal', 'Fees', 'Cost Basis', 'Cost/Unit']
        for col in dollar_columns:
            receive_display_df[col] = receive_display_df[col].apply(lambda x: f"${x:,.2f}")
        
        st.dataframe(receive_display_df, hide_index=True, use_container_width=True)
        
        # Download receive transfers CSV
        receive_csv = receive_transfers.to_csv(index=False)
        st.download_button(
            label="Download Receive Transfers (CSV)",
            data=receive_csv,
            file_name=f"receive_transfers_{selected_year}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv"
        )
    else:
        st.info("No receive transfers found")
    
    # Display summary statistics
    st.subheader("Summary Statistics")
    
    # Calculate summary metrics
    total_sent = send_transfers['subtotal'].sum() if not send_transfers.empty else 0
    total_received = receive_transfers['subtotal'].sum() if not receive_transfers.empty else 0
    total_send_fees = send_transfers['fees'].sum() if not send_transfers.empty else 0
    total_receive_fees = receive_transfers['fees'].sum() if not receive_transfers.empty else 0
    total_send_cost_basis = send_transfers['cost_basis'].sum() if not send_transfers.empty else 0
    total_receive_cost_basis = receive_transfers['cost_basis'].sum() if not receive_transfers.empty else 0
    
    # Display metrics in columns
    col1, col2 = st.columns(2)
    
    with col1:
        st.metric("Total Sent", format_currency(total_sent))
        st.metric("Total Send Fees", format_currency(total_send_fees))
        st.metric("Total Send Cost Basis", format_currency(total_send_cost_basis))
    
    with col2:
        st.metric("Total Received", format_currency(total_received))
        st.metric("Total Receive Fees", format_currency(total_receive_fees))
        st.metric("Total Receive Cost Basis", format_currency(total_receive_cost_basis))
    
    # Display net transfer amount
    net_transfer = total_received - total_sent
    st.metric("Net Transfer Amount", format_currency(net_transfer))

# Load data and display transfers
try:
    # Load transaction data
    transactions = pd.read_csv("output/transactions_normalized.csv", parse_dates=["timestamp"])
    if transactions.empty:
        st.error("No transaction data found.")
    else:
        # Initialize portfolio reporting with transactions
        reporter = PortfolioReporting(transactions)
        # Display transfers page
        display_transfers(reporter)
except Exception as e:
    st.error(f"Error loading transaction data: {str(e)}") 