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
    """Display transfer transactions with matching information"""
    st.title("Transfers")
    
    # Get all transfers
    transfers_df = reporter.get_transfer_transactions()
    
    # Add year filter
    years = ["All Years"] + sorted(transfers_df['timestamp'].dt.year.unique().tolist(), reverse=True)
    selected_year = st.selectbox("Select Year", years)
    
    # Filter by year if not "All Years"
    if selected_year != "All Years":
        transfers_df = transfers_df[transfers_df['timestamp'].dt.year == selected_year]
    
    # Add asset filter
    assets = ["All Assets"] + sorted(transfers_df['asset'].unique().tolist())
    selected_asset = st.selectbox("Select Asset", assets)
    
    # Filter by asset if not "All Assets"
    if selected_asset != "All Assets":
        transfers_df = transfers_df[transfers_df['asset'] == selected_asset]
    
    # Split into send and receive transfers
    send_df = transfers_df[transfers_df['type'] == 'transfer_out'].copy()
    receive_df = transfers_df[transfers_df['type'] == 'transfer_in'].copy()
    
    # Ensure quantities are displayed as positive for both send and receive
    send_df['quantity'] = send_df['quantity'].abs()
    receive_df['quantity'] = receive_df['quantity'].abs()
    
    # Ensure cost_basis column exists
    if 'cost_basis' not in send_df.columns:
        send_df['cost_basis'] = 0.0
    if 'cost_basis' not in receive_df.columns:
        receive_df['cost_basis'] = 0.0
    
    # Calculate cost basis per unit
    send_df['cost_basis_per_unit'] = send_df.apply(lambda row: row['cost_basis'] / row['quantity'] if row['quantity'] != 0 else 0, axis=1)
    receive_df['cost_basis_per_unit'] = receive_df.apply(lambda row: row['cost_basis'] / row['quantity'] if row['quantity'] != 0 else 0, axis=1)
    
    # Format and display send transfers
    st.header("Send Transfers")
    send_display_df = send_df[[
        'timestamp', 'asset', 'quantity', 'price', 'subtotal', 'fees',
        'cost_basis', 'cost_basis_per_unit', 'net_proceeds', 'institution'
    ]].copy()
    
    # Add destination and status columns if matching_institution exists
    if 'matching_institution' in send_df.columns:
        send_display_df['destination'] = send_df['matching_institution'].fillna('')
        send_display_df['status'] = send_df['matching_institution'].apply(
            lambda x: '✅ Matched' if pd.notna(x) else '❌ Unmatched'
        )
    else:
        send_display_df['destination'] = ''
        send_display_df['status'] = '❓ Unknown'
    
    # Rename columns and format timestamp
    send_display_df = send_display_df.rename(columns={
        'timestamp': 'Date',
        'asset': 'Asset',
        'quantity': 'Quantity',
        'price': 'Price',
        'subtotal': 'Subtotal',
        'fees': 'Fees',
        'cost_basis': 'Cost Basis',
        'cost_basis_per_unit': 'Cost/Unit',
        'net_proceeds': 'Net Proceeds',
        'institution': 'Source',
        'destination': 'Destination',
        'status': 'Status'
    })
    send_display_df['Date'] = send_display_df['Date'].dt.strftime('%Y-%m-%d')
    
    # Display send transfers
    st.dataframe(send_display_df.style.format({
        'Quantity': '{:.4f}',
        'Price': '${:.2f}',
        'Subtotal': '${:.2f}',
        'Fees': '${:.2f}',
        'Cost Basis': '${:.2f}',
        'Cost/Unit': '${:.2f}',
        'Net Proceeds': '${:.2f}'
    }))
    
    # Add download button for send transfers
    if not send_display_df.empty:
        csv = send_display_df.to_csv(index=False)
        year_suffix = f"_{selected_year}" if selected_year != "All Years" else "_all_years"
        asset_suffix = f"_{selected_asset}" if selected_asset != "All Assets" else "_all_assets"
        filename = f"send_transfers{year_suffix}{asset_suffix}.csv"
        st.download_button(
            "Download Send Transfers CSV",
            csv,
            filename,
            "text/csv",
            key='download-send-csv'
        )
    
    # Format and display receive transfers
    st.header("Receive Transfers")
    receive_display_df = receive_df[[
        'timestamp', 'asset', 'quantity', 'price', 'subtotal', 'fees',
        'cost_basis', 'cost_basis_per_unit', 'net_proceeds', 'institution'
    ]].copy()
    
    # Add source and status columns if matching_institution exists
    if 'matching_institution' in receive_df.columns:
        receive_display_df['source'] = receive_df['matching_institution'].fillna('')
        receive_display_df['status'] = receive_df['matching_institution'].apply(
            lambda x: '✅ Matched' if pd.notna(x) else '❌ Unmatched'
        )
    else:
        receive_display_df['source'] = ''
        receive_display_df['status'] = '❓ Unknown'
    
    # Rename columns and format timestamp
    receive_display_df = receive_display_df.rename(columns={
        'timestamp': 'Date',
        'asset': 'Asset',
        'quantity': 'Quantity',
        'price': 'Price',
        'subtotal': 'Subtotal',
        'fees': 'Fees',
        'cost_basis': 'Cost Basis',
        'cost_basis_per_unit': 'Cost/Unit',
        'net_proceeds': 'Net Proceeds',
        'institution': 'Destination',
        'source': 'Source',
        'status': 'Status'
    })
    receive_display_df['Date'] = receive_display_df['Date'].dt.strftime('%Y-%m-%d')
    
    # Display receive transfers
    st.dataframe(receive_display_df.style.format({
        'Quantity': '{:.4f}',
        'Price': '${:.2f}',
        'Subtotal': '${:.2f}',
        'Fees': '${:.2f}',
        'Cost Basis': '${:.2f}',
        'Cost/Unit': '${:.2f}',
        'Net Proceeds': '${:.2f}'
    }))
    
    # Add download button for receive transfers
    if not receive_display_df.empty:
        csv = receive_display_df.to_csv(index=False)
        year_suffix = f"_{selected_year}" if selected_year != "All Years" else "_all_years"
        asset_suffix = f"_{selected_asset}" if selected_asset != "All Assets" else "_all_assets"
        filename = f"receive_transfers{year_suffix}{asset_suffix}.csv"
        st.download_button(
            "Download Receive Transfers CSV",
            csv,
            filename,
            "text/csv",
            key='download-receive-csv'
        )

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