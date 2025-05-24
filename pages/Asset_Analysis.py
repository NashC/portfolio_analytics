import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import plotly.express as px
import plotly.graph_objects as go
from reporting import PortfolioReporting
from menu import render_navigation
from plotly.subplots import make_subplots
from streamlit.components.v1 import html
from app.analytics.portfolio import (
    compute_portfolio_time_series,
    compute_portfolio_time_series_with_external_prices
)
from app.services.price_service import PriceService

# Define helper functions for transaction analysis
def identify_internal_transfer(row, all_transactions):
    """Identify if a transfer is internal (between own accounts).
    
    Args:
        row: The transaction row to check
        all_transactions: All transactions dataframe
        
    Returns:
        bool: True if this is an internal transfer, False otherwise
    """
    # Only check transfer transactions
    if row['type'] not in ['transfer_in', 'transfer_out']:
        return False
        
    # Check if this transfer has a matching transaction in the opposite direction
    if 'transfer_id' in row and pd.notna(row['transfer_id']):
        # Look for a transaction with the same transfer_id but opposite type
        opposite_type = 'transfer_out' if row['type'] == 'transfer_in' else 'transfer_in'
        matching_txs = all_transactions[
            (all_transactions['transfer_id'] == row['transfer_id']) & 
            (all_transactions['type'] == opposite_type)
        ]
        
        if not matching_txs.empty:
            return True
    
    return False

def find_related_transaction(row, all_transactions):
    """Find the related transaction ID for a transfer.
    
    Args:
        row: The transaction row
        all_transactions: All transactions dataframe
        
    Returns:
        str: The related transaction ID or None
    """
    if row['type'] not in ['transfer_in', 'transfer_out'] or 'transfer_id' not in row or pd.isna(row['transfer_id']):
        return None
        
    # Find opposite transaction with same transfer_id
    opposite_type = 'transfer_out' if row['type'] == 'transfer_in' else 'transfer_in'
    matching_txs = all_transactions[
        (all_transactions['transfer_id'] == row['transfer_id']) & 
        (all_transactions['type'] == opposite_type)
    ]
    
    if not matching_txs.empty:
        return matching_txs.iloc[0]['transaction_id']
    
    return None

def get_transaction_type_color(transaction_type):
    """Return a color based on transaction type"""
    colors = {
        'buy': 'green',
        'sell': 'red',
        'transfer_in': 'blue',
        'transfer_out': 'orange',
        'staking_reward': 'purple',
        'swap': 'brown'
    }
    return colors.get(transaction_type, 'gray')

def get_transaction_type_symbol(transaction_type):
    """Return a plotly symbol based on transaction type"""
    symbols = {
        'buy': 'triangle-up',
        'sell': 'triangle-down',
        'transfer_in': 'arrow-up',
        'transfer_out': 'arrow-down',
        'staking_reward': 'star',
        'swap': 'diamond'
    }
    return symbols.get(transaction_type, 'circle')

# Must be the first Streamlit command
st.set_page_config(
    page_title="Asset Analysis",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Render navigation
render_navigation()

def load_data():
    """Load and validate transaction data"""
    try:
        transactions = pd.read_csv("output/transactions_normalized.csv", parse_dates=["timestamp"])
        if transactions.empty:
            st.error("No transaction data found.")
            return None
            
        # Convert asset column to string type to avoid comparison issues
        if 'asset' in transactions.columns:
            transactions['asset'] = transactions['asset'].astype(str)
            
        return transactions
    except Exception as e:
        st.error(f"Error loading transaction data: {str(e)}")
        return None

def display_price_chart(reporter, asset_symbol, price_data, transactions):
    """Display price chart with annotations for significant transactions"""
    st.subheader("Price History")
    
    if price_data is None or price_data.empty:
        st.warning(f"No price data available for {asset_symbol}.")
        return
    
    # Debug: Show available columns in price_data
    st.write(f"Available columns in price data: {list(price_data.columns)}")
    
    # Create price figure
    fig = go.Figure()
    
    # Add price line - use 'price' column instead of 'close' based on PortfolioReporting.get_price_data
    # First check if 'price' column exists, otherwise try 'close', then any numeric column
    price_column = None
    if 'price' in price_data.columns:
        price_column = 'price'
    elif 'close' in price_data.columns:
        price_column = 'close'
    else:
        # Find any numeric column that might contain price data
        for col in price_data.columns:
            if pd.api.types.is_numeric_dtype(price_data[col]):
                price_column = col
                break
    
    if price_column is None:
        st.error(f"No suitable price column found in the data. Available columns: {list(price_data.columns)}")
        return
    
    # Show which column is being used for the price
    st.info(f"Using column '{price_column}' for price data")
    
    # Add price line
    fig.add_trace(go.Scatter(
        x=price_data.index if price_data.index.name == 'date' else price_data['date'],
        y=price_data[price_column],
        mode='lines',
        name='Price',
        line=dict(color='royalblue', width=2),
        showlegend=False
    ))
    
    # Customize the layout
    fig.update_layout(
        xaxis_title='Date',
        yaxis_title='Price (USD)',
        height=400,
        margin=dict(l=20, r=20, t=30, b=30),
        hovermode='x unified',
        yaxis=dict(
            showgrid=True,
            gridcolor='rgba(230, 230, 230, 0.3)'
        )
    )
    
    # Display the chart
    st.plotly_chart(fig, use_container_width=True)
    
    # Now display the combined shareholding and transactions chart
    display_combined_shareholding_and_transactions(reporter, asset_symbol, transactions)
    
    # Display monthly balance changes (moved from Holdings tab)
    display_monthly_balance_changes(reporter, asset_symbol)

def display_combined_shareholding_and_transactions(reporter, asset_symbol, transactions):
    """Display combined shareholding history and significant transactions chart"""
    st.subheader("Shareholding History & Significant Transactions")
    
    # Filter transactions for the selected asset
    asset_transactions = transactions[transactions['asset'] == asset_symbol].copy()
    
    if asset_transactions.empty:
        st.warning(f"No transactions found for {asset_symbol}.")
        return
    
    # Ensure timestamps are datetime
    asset_transactions['timestamp'] = pd.to_datetime(asset_transactions['timestamp'])
    
    # Sort by timestamp
    asset_transactions = asset_transactions.sort_values('timestamp')
    
    # Calculate cumulative quantity over time
    asset_transactions['cumulative_quantity'] = asset_transactions['quantity'].cumsum()
    
    # Create a new column for internal transfers
    asset_transactions['is_internal_transfer'] = asset_transactions.apply(
        lambda row: identify_internal_transfer(row, transactions),
        axis=1
    )
    
    # Create adjusted quantity column that excludes internal transfers
    transfer_mask = asset_transactions['is_internal_transfer']
    asset_transactions['adjusted_quantity'] = asset_transactions['quantity'].copy()
    asset_transactions.loc[transfer_mask, 'adjusted_quantity'] = 0
    asset_transactions['adjusted_cumulative'] = asset_transactions['adjusted_quantity'].cumsum()
    
    # Create figure for combined chart
    fig = go.Figure()
    
    # Add shareholding history line (using adjusted cumulative that excludes internal transfers)
    fig.add_trace(go.Scatter(
        x=asset_transactions['timestamp'],
        y=asset_transactions['adjusted_cumulative'],
        mode='lines',
        name='Holdings',
        line=dict(color='rgba(0, 128, 0, 0.7)', width=2),
        fill='tozeroy',
        fillcolor='rgba(0, 128, 0, 0.2)'
    ))
    
    # Define significant transaction types to annotate (include transfers)
    significant_types = ['buy', 'sell', 'transfer_in', 'transfer_out', 'staking_reward', 'swap']
    
    # Create annotations for significant transactions
    for tx_type in significant_types:
        type_txs = asset_transactions[asset_transactions['type'] == tx_type]
        
        if not type_txs.empty:
            fig.add_trace(go.Scatter(
                x=type_txs['timestamp'],
                y=type_txs['adjusted_cumulative'],
                mode='markers',
                name=tx_type.replace('_', ' ').title(),
                marker=dict(
                    symbol=get_transaction_type_symbol(tx_type),
                    color=get_transaction_type_color(tx_type),
                    size=10,
                    line=dict(width=1, color='white')
                ),
                hovertemplate='<b>%{text}</b><extra></extra>',
                text=[
                    f"{tx_type.replace('_', ' ').title()}<br>" +
                    f"Date: {ts.strftime('%Y-%m-%d')}<br>" +
                    f"Quantity: {qty:.8f}<br>" +
                    f"Balance: {bal:.8f}"
                    for ts, qty, bal in zip(
                        type_txs['timestamp'], 
                        type_txs['quantity'], 
                        type_txs['adjusted_cumulative']
                    )
                ]
            ))
    
    # Customize the layout
    fig.update_layout(
        xaxis_title='Date',
        yaxis_title='Quantity',
        height=350,
        margin=dict(l=20, r=20, t=30, b=30),
        hovermode='closest',
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        )
    )
    
    # Display the chart
    st.plotly_chart(fig, use_container_width=True)

def display_transaction_history(reporter, asset_symbol, years=None, transaction_types=None):
    """Display transaction history for a specific asset with filtering options"""
    # Get transactions for the selected asset
    asset_transactions = reporter.transactions[reporter.transactions['asset'] == asset_symbol].copy()
    
    if asset_transactions.empty:
        st.warning(f"No transactions found for {asset_symbol}.")
        return asset_transactions
    
    # Ensure timestamp is datetime
    asset_transactions['timestamp'] = pd.to_datetime(asset_transactions['timestamp'])
    
    # Apply year filter if provided
    if years and not ("All Years" in years):
        year_filters = [asset_transactions['timestamp'].dt.year == int(year) for year in years]
        combined_filter = year_filters[0]
        for year_filter in year_filters[1:]:
            combined_filter = combined_filter | year_filter
        asset_transactions = asset_transactions[combined_filter]
    
    # Apply transaction type filter if provided
    if transaction_types and not ("All Types" in transaction_types):
        asset_transactions = asset_transactions[asset_transactions['type'].isin(transaction_types)]
    
    # Check if we have transactions after filtering
    if asset_transactions.empty:
        st.warning(f"No transactions found matching the selected filters.")
        return asset_transactions
    
    # Sort by timestamp (newest first)
    asset_transactions = asset_transactions.sort_values('timestamp', ascending=False)
    
    # Add information about related transactions for transfers
    asset_transactions['related_transaction'] = asset_transactions.apply(
        lambda row: find_related_transaction(row, reporter.transactions) if row['type'] in ['transfer_in', 'transfer_out'] else None,
        axis=1
    )
    
    # Create a cleaned version of the dataframe for display
    display_df = asset_transactions.copy()
    
    # Format timestamp as date
    display_df['timestamp'] = display_df['timestamp'].dt.strftime('%Y-%m-%d')
    
    # Format quantity with 8 decimal places
    display_df['quantity'] = display_df['quantity'].apply(lambda x: f"{x:.8f}")
    
    # Format transaction type
    display_df['type'] = display_df['type'].apply(lambda x: x.replace('_', ' ').title())
    
    # Prepare cost basis information
    display_df['Cost Basis'] = ""
    
    # Ensure Exchange column exists
    if 'exchange' not in display_df.columns:
        display_df['exchange'] = "Unknown"
    
    # Ensure Notes column exists
    if 'notes' not in display_df.columns:
        display_df['notes'] = ""
    
    # Calculate running balance
    all_tx_for_balance = reporter.transactions[reporter.transactions['asset'] == asset_symbol].copy()
    all_tx_for_balance['timestamp'] = pd.to_datetime(all_tx_for_balance['timestamp'])
    all_tx_for_balance = all_tx_for_balance.sort_values('timestamp')
    all_tx_for_balance['balance'] = all_tx_for_balance['quantity'].cumsum()
    
    # Merge balance into display dataframe
    balance_map = all_tx_for_balance.set_index('transaction_id')['balance'].to_dict()
    display_df['Balance'] = display_df['transaction_id'].map(balance_map).apply(lambda x: f"{x:.8f}" if pd.notna(x) else "")
    
    # For transfers, add information about source or destination
    display_df['Transfer Info'] = ""
    for idx, row in display_df.iterrows():
        if row['type'] in ['Transfer In', 'Transfer Out']:
            related_tx_id = row['related_transaction']
            if related_tx_id:
                related_tx = reporter.transactions[reporter.transactions['transaction_id'] == related_tx_id]
                if not related_tx.empty:
                    related_exchange = related_tx.iloc[0].get('exchange', 'Unknown')
                    current_exchange = row.get('exchange', 'Unknown')
                    
                    if pd.isna(related_exchange):
                        related_exchange = 'Unknown'
                    if pd.isna(current_exchange):
                        current_exchange = 'Unknown'
                    
                    if row['type'] == 'Transfer In':
                        display_df.at[idx, 'Transfer Info'] = f"From {related_exchange} to {current_exchange}"
                    else:  # Transfer Out
                        display_df.at[idx, 'Transfer Info'] = f"From {current_exchange} to {related_exchange}"
    
    # Try to calculate cost basis for specific transaction types
    for idx, row in display_df.iterrows():
        if row['type'] == 'Sell':
            try:
                tx_id = asset_transactions.iloc[idx]['transaction_id']
                tax_lots = reporter.calculate_tax_lots()
                if not tax_lots.empty:
                    tx_tax_lots = tax_lots[tax_lots['disposal_transaction_id'] == tx_id]
                    if not tx_tax_lots.empty:
                        cost_basis = tx_tax_lots['cost_basis'].sum()
                        display_df.at[idx, 'Cost Basis'] = f"${cost_basis:.2f}"
            except:
                pass
        elif row['type'] == 'Transfer In':
            # Try to get cost basis from the related transaction (if it's a transfer_out)
            try:
                tx_id = asset_transactions.iloc[idx]['transaction_id']
                related_tx_id = asset_transactions.iloc[idx]['related_transaction']
                
                if related_tx_id:
                    related_tx = reporter.transactions[reporter.transactions['transaction_id'] == related_tx_id]
                    if not related_tx.empty and related_tx.iloc[0]['type'] == 'transfer_out':
                        # Get all previous acquisitions up to the transfer_out timestamp
                        prior_date = pd.to_datetime(related_tx.iloc[0]['timestamp'])
                        asset_symbol = related_tx.iloc[0]['asset']
                        quantity = abs(related_tx.iloc[0]['quantity'])
                        
                        prior_acquisitions = reporter.transactions[
                            (reporter.transactions['asset'] == asset_symbol) & 
                            (pd.to_datetime(reporter.transactions['timestamp']) < prior_date) &
                            (reporter.transactions['type'].isin(['buy', 'transfer_in', 'staking_reward']))
                        ].copy()
                        
                        if not prior_acquisitions.empty:
                            # Calculate cost per unit
                            prior_acquisitions['cost'] = prior_acquisitions.apply(
                                lambda r: abs(r['quantity']) * (
                                    r['price'] if pd.notna(r['price']) and r['type'] != 'transfer_in' else 0), 
                                axis=1
                            )
                            
                            total_cost = prior_acquisitions['cost'].sum()
                            total_quantity = prior_acquisitions['quantity'].sum()
                            
                            if total_quantity > 0:
                                cost_per_unit = total_cost / total_quantity
                                cost_basis = cost_per_unit * quantity
                                display_df.at[idx, 'Cost Basis'] = f"${cost_basis:.2f}"
            except:
                pass
    
    # Make sure all required columns for display exist
    required_columns = ['timestamp', 'type', 'quantity', 'price', 'Cost Basis', 'Transfer Info', 'Balance']
    
    # Make sure Exchange and Notes columns are properly cased
    if 'exchange' in display_df.columns:
        display_df['Exchange'] = display_df['exchange']
    else:
        display_df['Exchange'] = "Unknown"
        
    if 'notes' in display_df.columns:
        display_df['Notes'] = display_df['notes']
    else:
        display_df['Notes'] = ""
    
    # Collect all columns that actually exist
    display_columns = [col for col in ['timestamp', 'type', 'quantity', 'price', 'Cost Basis', 'Exchange', 'Transfer Info', 'Balance', 'Notes'] 
                      if col in display_df.columns]
    
    # Display the transaction history
    st.subheader("Transaction History")
    st.dataframe(
        display_df[display_columns],
        use_container_width=True,
        hide_index=True,
        column_config={
            "timestamp": st.column_config.TextColumn("Date", width="small"),
            "type": st.column_config.TextColumn("Type", width="small"),
            "quantity": st.column_config.TextColumn("Quantity", width="small"),
            "price": st.column_config.NumberColumn("Price (USD)", format="$%.2f", width="small"),
            "Cost Basis": st.column_config.TextColumn(width="small"),
            "Exchange": st.column_config.TextColumn(width="small"),
            "Transfer Info": st.column_config.TextColumn(width="medium"),
            "Balance": st.column_config.TextColumn(width="medium"),
            "Notes": st.column_config.TextColumn(width="large")
        }
    )
    
    # Add a Tax Lot Analysis header before transaction selection
    st.markdown("---")
    st.subheader("🧾 Tax Lots Analysis")
    st.write("Select a transaction to view tax lot details:")
    
    # Set up transaction selection for tax lot analysis
    # Modified to include transfer_in and transfer_out in addition to sell transactions
    eligible_types = ['sell', 'transfer_in', 'transfer_out']
    eligible_transactions = asset_transactions[asset_transactions['type'].isin(eligible_types)]
    
    if not eligible_transactions.empty:
        # Process transfer information for dropdown display
        tx_options = []
        for _, tx in eligible_transactions.iterrows():
            # Format date and transaction type
            date_str = tx['timestamp'].strftime('%Y-%m-%d')
            tx_type = tx['type'].replace('_', ' ').title()
            
            # Format quantity
            quantity_str = f"{abs(tx['quantity']):.8f} {asset_symbol}"
            
            # Add exchange information for transfers
            exchange_info = ""
            if tx['type'] in ['transfer_in', 'transfer_out']:
                # Get this transaction's exchange
                this_exchange = tx.get('exchange', 'Unknown')
                if pd.isna(this_exchange):
                    this_exchange = "Unknown"
                
                # If this is a transfer, try to find the related transaction for its exchange
                related_tx_id = find_related_transaction(tx, reporter.transactions)
                if related_tx_id:
                    related_tx = reporter.transactions[reporter.transactions['transaction_id'] == related_tx_id]
                    if not related_tx.empty:
                        related_exchange = related_tx.iloc[0].get('exchange', 'Unknown')
                        if pd.isna(related_exchange):
                            related_exchange = "Unknown"
                            
                        if tx['type'] == 'transfer_in':
                            exchange_info = f" (From: {related_exchange} To: {this_exchange})"
                        else:  # transfer_out
                            exchange_info = f" (From: {this_exchange} To: {related_exchange})"
            
            # Combine all information
            tx_options.append(f"{date_str} - {tx_type} - {quantity_str}{exchange_info}")
        
        # Add a "None" option as the default
        tx_options = ["No transaction selected"] + tx_options
        
        selected_idx = st.selectbox(
            "Transaction",
            options=range(len(tx_options)),
            format_func=lambda i: tx_options[i],
            key="transaction_selector",
            index=0  # Default to the "None" option
        )
        
        # Only display tax lots if a valid transaction is selected (not the "None" option)
        if selected_idx > 0:
            # Adjust index to account for the added "None" option
            actual_idx = selected_idx - 1
            selected_tx_id = eligible_transactions.iloc[actual_idx]['transaction_id']
            st.session_state.selected_transaction_id = selected_tx_id
            
            # Display the tax lots for the selected transaction
            selected_tx = asset_transactions[asset_transactions['transaction_id'] == selected_tx_id]
            if not selected_tx.empty and selected_tx.iloc[0]['type'] in eligible_types:
                display_tax_lots_for_transaction(reporter, selected_tx_id)
    
    return asset_transactions

def display_tax_lots_for_transaction(reporter, transaction_id):
    """Display tax lots for a selected transaction"""
    # Get the transaction
    transaction = reporter.transactions[reporter.transactions['transaction_id'] == transaction_id]
    
    if transaction.empty:
        st.warning("Transaction not found.")
        return
    
    # Get the first transaction (should be only one with this ID)
    transaction = transaction.iloc[0]
    transaction_type = transaction['type']
    asset_symbol = transaction['asset']
    transaction_date = pd.to_datetime(transaction['timestamp']).date()
    quantity = abs(transaction['quantity'])
    price = transaction['price'] if pd.notna(transaction['price']) else 0.0
    
    # Show transaction summary
    st.write(f"### Tax Lots for {transaction_type.replace('_', ' ').title()} Transaction on {transaction_date}")
    
    # Create a summary box with transaction details
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Type", transaction_type.replace('_', ' ').title())
    with col2:
        st.metric("Date", str(transaction_date))
    with col3:
        st.metric("Quantity", f"{quantity:.8f} {asset_symbol}")
    with col4:
        st.metric("Price", f"${price:.2f}" if price > 0 else "N/A")
    
    # For sell transactions, display traditional tax lots
    if transaction_type == 'sell':
        # Get the tax lots for this transaction
        tax_lots = reporter.calculate_tax_lots()
        
        if tax_lots.empty:
            st.warning("No tax lots found.")
            return
        
        # Filter tax lots for this transaction
        tx_tax_lots = tax_lots[tax_lots['disposal_transaction_id'] == transaction_id]
        
        if tx_tax_lots.empty:
            st.warning("No tax lots found for this transaction.")
            return
        
        # Create a formatted display dataframe
        display_df = tx_tax_lots.copy()
        
        # Format timestamps
        if 'acquisition_date' in display_df.columns:
            display_df['acquisition_date'] = pd.to_datetime(display_df['acquisition_date']).dt.strftime('%Y-%m-%d')
        if 'disposal_date' in display_df.columns:
            display_df['disposal_date'] = pd.to_datetime(display_df['disposal_date']).dt.strftime('%Y-%m-%d')
        
        # Format numeric columns
        display_df['quantity'] = display_df['quantity'].apply(lambda x: f"{float(x):.8f}" if isinstance(x, (int, float)) else f"{float(str(x).replace(',', '')):.8f}")
        display_df['cost_basis'] = display_df['cost_basis'].apply(lambda x: f"${float(x):.2f}" if isinstance(x, (int, float)) else f"${float(str(x).replace('$', '').replace(',', '')):.2f}")
        display_df['proceeds'] = display_df['proceeds'].apply(lambda x: f"${float(x):.2f}" if isinstance(x, (int, float)) else f"${float(str(x).replace('$', '').replace(',', '')):.2f}")
        display_df['gain_loss'] = display_df['gain_loss'].apply(lambda x: f"${float(x):.2f}" if isinstance(x, (int, float)) else f"${float(str(x).replace('$', '').replace(',', '')):.2f}")
        
        # Safely parse numeric values for calculations
        def parse_numeric(value):
            if isinstance(value, (int, float)):
                return float(value)
            elif isinstance(value, str):
                return float(value.replace('$', '').replace(',', ''))
            return 0.0
        
        # Calculate per-unit metrics safely
        display_df['cost_per_unit'] = display_df.apply(
            lambda row: parse_numeric(row['cost_basis']) / parse_numeric(row['quantity']) if parse_numeric(row['quantity']) > 0 else 0, 
            axis=1
        ).apply(lambda x: f"${x:.4f}")
        
        display_df['proceeds_per_unit'] = display_df.apply(
            lambda row: parse_numeric(row['proceeds']) / parse_numeric(row['quantity']) if parse_numeric(row['quantity']) > 0 else 0, 
            axis=1
        ).apply(lambda x: f"${x:.4f}")
        
        # Rename columns for better readability
        display_df = display_df.rename(columns={
            'acquisition_date': 'Acquisition Date',
            'acquisition_type': 'Acquisition Type',
            'acquisition_exchange': 'Acquisition Exchange',
            'disposal_date': 'Disposal Date',
            'quantity': 'Quantity',
            'cost_basis': 'Cost Basis',
            'proceeds': 'Proceeds',
            'gain_loss': 'Gain/Loss',
            'cost_per_unit': 'Cost/Unit',
            'proceeds_per_unit': 'Proceeds/Unit',
            'holding_period_days': 'Holding Period (Days)'
        })
        
        # Display the tax lots for the selected transaction
        st.dataframe(display_df, use_container_width=True, hide_index=True)
        
        # Calculate and display totals
        st.write("### Tax Lot Summary")
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            total_quantity = sum(parse_numeric(q) for q in tx_tax_lots['quantity'])
            st.metric("Total Quantity", f"{total_quantity:.8f}")
        
        with col2:
            total_cost = sum(parse_numeric(c) for c in tx_tax_lots['cost_basis'])
            st.metric("Total Cost Basis", f"${total_cost:.2f}")
        
        with col3:
            total_proceeds = sum(parse_numeric(p) for p in tx_tax_lots['proceeds'])
            st.metric("Total Proceeds", f"${total_proceeds:.2f}")
        
        with col4:
            total_gain_loss = sum(parse_numeric(g) for g in tx_tax_lots['gain_loss'])
            st.metric("Total Gain/Loss", f"${total_gain_loss:.2f}")
    
    # For transfer transactions (transfer_in or transfer_out), show contributing acquisitions
    elif transaction_type in ['transfer_in', 'transfer_out']:
        st.subheader("Cost Basis Analysis")
        
        # Find related transaction
        related_tx_id = find_related_transaction(transaction, reporter.transactions)
        related_exchange = "Unknown"
        
        if related_tx_id:
            related_tx = reporter.transactions[reporter.transactions['transaction_id'] == related_tx_id]
            if not related_tx.empty:
                related_exchange = related_tx.iloc[0].get('exchange', 'Unknown')
                if pd.isna(related_exchange):
                    related_exchange = "Unknown"
        
        # Display transfer details
        col1, col2 = st.columns(2)
        with col1:
            if transaction_type == 'transfer_in':
                st.info(f"Transfer In from {related_exchange} to {transaction.get('exchange', 'Unknown')}")
            else:
                st.info(f"Transfer Out from {transaction.get('exchange', 'Unknown')} to {related_exchange}")
        
        # Get all acquisitions before this transfer
        prior_date = pd.to_datetime(transaction['timestamp'])
        
        # For transfer_out, we analyze acquisitions before the transfer date
        if transaction_type == 'transfer_out':
            prior_acquisitions = reporter.transactions[
                (reporter.transactions['asset'] == asset_symbol) & 
                (pd.to_datetime(reporter.transactions['timestamp']) < prior_date) &
                (reporter.transactions['type'].isin(['buy', 'transfer_in', 'staking_reward']))
            ].copy()
            
            if prior_acquisitions.empty:
                st.warning("No prior acquisitions found for this asset before the transfer.")
                return
            
            # Calculate cost for each acquisition
            prior_acquisitions['cost'] = prior_acquisitions.apply(
                lambda row: abs(row['quantity']) * (
                    row['price'] if pd.notna(row['price']) and row['type'] != 'transfer_in' else 
                    (row.get('cost_basis', 0) / abs(row['quantity']) if pd.notna(row.get('cost_basis', 0)) and abs(row['quantity']) > 0 else 0)
                ), 
                axis=1
            )
            
            # Calculate total quantity and cost
            total_quantity = prior_acquisitions['quantity'].sum()
            total_cost = prior_acquisitions['cost'].sum()
            
            if total_quantity > 0:
                avg_cost_basis = total_cost / total_quantity
                total_cost_basis = quantity * avg_cost_basis
                
                # Display cost basis information
                st.subheader("Cost Basis Information")
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.metric("Average Cost Basis", f"${avg_cost_basis:.4f} per unit")
                
                with col2:
                    st.metric("Transfer Quantity", f"{quantity:.8f}")
                
                with col3:
                    st.metric("Total Cost Basis", f"${total_cost_basis:.2f}")
            
            # Format acquisitions for display
            display_acquisitions = prior_acquisitions.copy()
            
            # Format timestamp
            display_acquisitions['timestamp'] = pd.to_datetime(display_acquisitions['timestamp']).dt.strftime('%Y-%m-%d')
            
            # Format transaction type
            display_acquisitions['type'] = display_acquisitions['type'].apply(
                lambda x: "Staking Reward" if x == "staking_reward" or x == "staking_rewards" 
                else x.replace('_', ' ').title() if pd.notna(x) else "Unknown"
            )
            
            # Format numeric columns
            display_acquisitions['quantity'] = display_acquisitions['quantity'].apply(lambda x: f"{float(x):.8f}")
            display_acquisitions['price'] = display_acquisitions['price'].apply(lambda x: f"${float(x):.2f}" if pd.notna(x) else "$0.00")
            display_acquisitions['cost'] = display_acquisitions['cost'].apply(lambda x: f"${float(x):.2f}")
            
            # Add a column for exchange
            if 'exchange' not in display_acquisitions.columns:
                display_acquisitions['exchange'] = "Unknown"
            
            # Rename columns for display
            display_acquisitions = display_acquisitions.rename(columns={
                'timestamp': 'Date',
                'type': 'Type',
                'quantity': 'Quantity',
                'price': 'Price',
                'cost': 'Cost',
                'exchange': 'Exchange'
            })
            
            # Select columns to display
            display_cols = ['Date', 'Type', 'Quantity', 'Price', 'Cost', 'Exchange']
            display_cols = [col for col in display_cols if col in display_acquisitions.columns]
            
            # Show contributing acquisitions
            st.subheader("Contributing Acquisitions")
            st.dataframe(
                display_acquisitions[display_cols], 
                use_container_width=True,
                hide_index=True
            )
        
        # For transfer_in, show information about the source if available
        elif transaction_type == 'transfer_in':
            if related_tx_id:
                related_tx = reporter.transactions[reporter.transactions['transaction_id'] == related_tx_id]
                if not related_tx.empty:
                    # Get information about the source transaction
                    source_tx = related_tx.iloc[0]
                    source_date = pd.to_datetime(source_tx['timestamp']).date()
                    source_exchange = source_tx.get('exchange', 'Unknown')
                    if pd.isna(source_exchange):
                        source_exchange = "Unknown"
                    
                    st.subheader("Source Transaction Information")
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        st.metric("Source Exchange", source_exchange)
                    
                    with col2:
                        st.metric("Source Date", str(source_date))
                    
                    with col3:
                        st.metric("Source Quantity", f"{abs(source_tx['quantity']):.8f}")
                    
                    # Try to find cost basis information for the source transaction
                    prior_to_source = reporter.transactions[
                        (reporter.transactions['asset'] == asset_symbol) & 
                        (pd.to_datetime(reporter.transactions['timestamp']) < pd.to_datetime(source_tx['timestamp'])) &
                        (reporter.transactions['type'].isin(['buy', 'transfer_in', 'staking_reward']))
                    ].copy()
                    
                    if not prior_to_source.empty:
                        # Calculate cost for acquisitions prior to source transaction
                        prior_to_source['cost'] = prior_to_source.apply(
                            lambda row: abs(row['quantity']) * (
                                row['price'] if pd.notna(row['price']) and row['type'] != 'transfer_in' else 
                                (row.get('cost_basis', 0) / abs(row['quantity']) if pd.notna(row.get('cost_basis', 0)) and abs(row['quantity']) > 0 else 0)
                            ), 
                            axis=1
                        )
                        
                        total_quantity = prior_to_source['quantity'].sum()
                        total_cost = prior_to_source['cost'].sum()
                        
                        if total_quantity > 0:
                            avg_cost_basis = total_cost / total_quantity
                            total_cost_basis = quantity * avg_cost_basis
                            
                            st.subheader("Estimated Cost Basis Information")
                            col1, col2, col3 = st.columns(3)
                            
                            with col1:
                                st.metric("Estimated Cost/Unit", f"${avg_cost_basis:.4f}")
                            
                            with col2:
                                st.metric("Transfer Quantity", f"{quantity:.8f}")
                            
                            with col3:
                                st.metric("Estimated Cost Basis", f"${total_cost_basis:.2f}")
                            
                            # Show the contributing acquisitions
                            st.subheader("Contributing Acquisitions")
                            
                            # Format acquisitions for display
                            display_source = prior_to_source.copy()
                            
                            # Format timestamp
                            display_source['timestamp'] = pd.to_datetime(display_source['timestamp']).dt.strftime('%Y-%m-%d')
                            
                            # Format transaction type
                            display_source['type'] = display_source['type'].apply(
                                lambda x: "Staking Reward" if x == "staking_reward" or x == "staking_rewards" 
                                else x.replace('_', ' ').title() if pd.notna(x) else "Unknown"
                            )
                            
                            # Format numeric columns
                            display_source['quantity'] = display_source['quantity'].apply(lambda x: f"{float(x):.8f}")
                            display_source['price'] = display_source['price'].apply(lambda x: f"${float(x):.2f}" if pd.notna(x) else "$0.00")
                            display_source['cost'] = display_source['cost'].apply(lambda x: f"${float(x):.2f}")
                            
                            # Add a column for exchange
                            if 'exchange' not in display_source.columns:
                                display_source['exchange'] = "Unknown"
                            
                            # Rename columns for display
                            display_source = display_source.rename(columns={
                                'timestamp': 'Date',
                                'type': 'Type',
                                'quantity': 'Quantity',
                                'price': 'Price',
                                'cost': 'Cost',
                                'exchange': 'Exchange'
                            })
                            
                            # Select columns to display
                            display_cols = ['Date', 'Type', 'Quantity', 'Price', 'Cost', 'Exchange']
                            display_cols = [col for col in display_cols if col in display_source.columns]
                            
                            # Show contributing acquisitions
                            st.dataframe(
                                display_source[display_cols], 
                                use_container_width=True,
                                hide_index=True
                            )
                    else:
                        st.warning("No prior acquisitions found to calculate cost basis for this transfer.")
                else:
                    st.warning("Could not find details for the source transaction.")
            else:
                st.warning("No related transaction found for this transfer. Cannot determine source information.")
    else:
        st.warning(f"Tax lots analysis not available for {transaction_type} transactions.")

def display_monthly_balance_changes(reporter, asset_symbol):
    """Display monthly balance changes for a specific asset"""
    # Get transactions for this asset
    asset_transactions = reporter.transactions[reporter.transactions['asset'] == asset_symbol].copy()
    
    if asset_transactions.empty:
        st.warning(f"No transactions found for {asset_symbol}.")
        return
    
    # Add a year-month column
    asset_transactions['timestamp'] = pd.to_datetime(asset_transactions['timestamp'])
    asset_transactions['year_month'] = asset_transactions['timestamp'].dt.strftime('%Y-%m')
    
    # Create a new column for internal transfers
    asset_transactions['is_internal_transfer'] = asset_transactions.apply(
        lambda row: identify_internal_transfer(row, reporter.transactions),
        axis=1
    )
    
    # Filter out internal transfers for analysis
    analysis_txs = asset_transactions[~asset_transactions['is_internal_transfer']].copy()
    
    # Group by year-month and transaction type
    monthly_changes = analysis_txs.groupby(['year_month', 'type'])['quantity'].sum().reset_index()
    
    # Pivot to get transaction types as columns
    pivot_changes = monthly_changes.pivot(index='year_month', columns='type', values='quantity').reset_index()
    
    # Replace NaN with 0
    pivot_changes = pivot_changes.fillna(0)
    
    # Make sure we have all the common transaction types
    for tx_type in ['buy', 'sell', 'staking_reward', 'transfer_in', 'transfer_out']:
        if tx_type not in pivot_changes.columns:
            pivot_changes[tx_type] = 0
    
    # Convert year_month to datetime for sorting
    pivot_changes['date'] = pd.to_datetime(pivot_changes['year_month'] + '-01')
    pivot_changes = pivot_changes.sort_values('date')
    
    # Create the stacked bar chart
    st.subheader("Monthly Balance Changes")
    
    # Check if there are significant changes
    if (pivot_changes[['buy', 'sell', 'staking_reward', 'transfer_in', 'transfer_out']].abs() > 0.00000001).any().any():
        fig = go.Figure()
        
        # Add traces for each transaction type
        for tx_type in ['buy', 'sell', 'staking_reward', 'transfer_in', 'transfer_out']:
            if tx_type in pivot_changes.columns:
                fig.add_trace(go.Bar(
                    x=pivot_changes['date'],
                    y=pivot_changes[tx_type],
                    name=tx_type.replace('_', ' ').title(),
                    marker_color=get_transaction_type_color(tx_type)
                ))
        
        # Customize layout
        fig.update_layout(
            barmode='relative',
            title=f"Monthly Balance Changes for {asset_symbol}",
            xaxis_title="Month",
            yaxis_title="Quantity",
            legend_title="Transaction Type",
            height=350
        )
        
        # Update x-axis to show month-year format
        fig.update_xaxes(
            tickformat="%b %Y",
            tickangle=-45
        )
        
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No significant monthly balance changes found.")

def display_transaction_statistics(reporter, asset_symbol, transactions):
    """Display statistical analysis of transactions for an asset"""
    if transactions.empty:
        st.warning(f"No transactions found for {asset_symbol}.")
        return
        
    with st.expander("Transaction Statistics & Patterns", expanded=True):
        st.write("### Transaction Statistics")
        
        # Add a summary row with key metrics
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric(
                "Total Transactions", 
                f"{len(transactions)}", 
                help="Total number of transactions for this asset"
            )
        with col2:
            tx_types_count = len(transactions['type'].unique())
            st.metric(
                "Transaction Types", 
                f"{tx_types_count}", 
                help="Number of different transaction types"
            )
        with col3:
            earliest = pd.to_datetime(transactions['timestamp'].min()).strftime('%Y-%m-%d')
            st.metric(
                "First Transaction", 
                f"{earliest}", 
                help="Date of the first transaction"
            )
        with col4:
            tx_period = (pd.to_datetime(transactions['timestamp'].max()) - 
                        pd.to_datetime(transactions['timestamp'].min())).days
            st.metric(
                "Trading Period", 
                f"{tx_period} days", 
                help="Number of days between first and last transaction"
            )
        
        # Count transactions by type
        tx_counts = transactions['type'].value_counts().reset_index()
        tx_counts.columns = ['Type', 'Count']
        
        col1, col2 = st.columns([3, 2])
        
        with col1:
            # Create pie chart of transaction types with improved colors and formatting
            fig = px.pie(
                tx_counts, 
                values='Count', 
                names='Type',
                title='Transaction Types Distribution',
                color='Type',
                color_discrete_map={
                    'buy': 'green',
                    'sell': 'red',
                    'transfer_in': 'blue',
                    'transfer_out': 'orange',
                    'staking_reward': 'purple',
                    'swap': 'brown'
                },
                hole=0.4  # Make it a donut chart for better appearance
            )
            
            # Improve pie chart appearance
            fig.update_traces(
                textposition='inside',
                textinfo='percent+label',
                hovertemplate='<b>%{label}</b><br>Count: %{value}<br>Percentage: %{percent}'
            )
            
            fig.update_layout(
                showlegend=False,  # Hide legend as it's shown in the text
                uniformtext_minsize=12,
                uniformtext_mode='hide'
            )
            
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            # Display transaction counts with percentage
            tx_counts['Percentage'] = (tx_counts['Count'] / tx_counts['Count'].sum() * 100).round(1).astype(str) + '%'
            st.write("Transaction Counts by Type")
            st.dataframe(tx_counts, use_container_width=True, hide_index=True)
            
            # Calculate total volume with better formatting
            total_volume = transactions[transactions['type'].isin(['buy', 'sell'])]['quantity'].abs().sum()
            st.metric("Total Trading Volume", f"{total_volume:.8f}")

        # Transaction volume over time
        st.write("### Volume Over Time")
        
        # Ensure timestamp is datetime
        transactions['timestamp'] = pd.to_datetime(transactions['timestamp'])
        
        # Group by month and type
        transactions['year_month'] = transactions['timestamp'].dt.to_period('M')
        monthly_tx = transactions.groupby(['year_month', 'type']).agg(
            count=('transaction_id', 'count'),
            volume=('quantity', lambda x: abs(x).sum())
        ).reset_index()
        monthly_tx['year_month'] = monthly_tx['year_month'].dt.to_timestamp()
        
        # Monthly transaction volume
        fig = px.bar(
            monthly_tx,
            x='year_month',
            y='volume',
            color='type',
            title="Monthly Transaction Volume by Type",
            labels={'year_month': 'Month', 'volume': 'Volume', 'type': 'Transaction Type'},
            color_discrete_map={
                'buy': 'green',
                'sell': 'red',
                'transfer_in': 'blue',
                'transfer_out': 'orange',
                'staking_reward': 'purple',
                'swap': 'brown'
            }
        )
        
        # Improve monthly volume chart formatting
        fig.update_layout(
            xaxis_tickformat='%b %Y',
            bargap=0.2,
            bargroupgap=0.1,
            hovermode='closest',
            xaxis_title='Month',
            yaxis_title='Volume',
            legend_title='Transaction Type',
        )
        
        st.plotly_chart(fig, use_container_width=True)

def calculate_returns(prices: pd.Series) -> pd.Series:
    """Calculate daily returns from price series"""
    return prices.pct_change().dropna()

def calculate_volatility(returns: pd.Series) -> float:
    """Calculate annualized volatility from daily returns"""
    return returns.std() * np.sqrt(252) * 100  # Annualized and as percentage

def calculate_sharpe_ratio(returns: pd.Series, risk_free_rate: float = 0.02) -> float:
    """Calculate Sharpe ratio from daily returns"""
    excess_returns = returns - risk_free_rate/252  # Daily risk-free rate
    return np.sqrt(252) * excess_returns.mean() / returns.std()

def calculate_max_drawdown(prices: pd.Series) -> float:
    """Calculate maximum drawdown from price series"""
    rolling_max = prices.expanding().max()
    drawdowns = (prices - rolling_max) / rolling_max
    return drawdowns.min() * 100  # As percentage

def calculate_best_worst_day(returns: pd.Series) -> tuple:
    """Calculate best and worst daily returns"""
    return returns.max() * 100, returns.min() * 100  # As percentages

def display_asset_analysis(transactions: pd.DataFrame):
    """Display detailed analysis for each asset"""
    st.header("Asset Analysis")
    
    # Get unique assets
    assets = sorted(transactions['asset'].unique())
    selected_asset = st.selectbox("Select Asset", assets)
    
    if not selected_asset:
        st.warning("No asset selected")
        return
    
    # Filter transactions for selected asset
    asset_transactions = transactions[transactions['asset'] == selected_asset].copy()
    
    if asset_transactions.empty:
        st.warning(f"No transactions found for {selected_asset}")
        return
    
    # Calculate portfolio value over time
    portfolio_value = compute_portfolio_time_series_with_external_prices(asset_transactions)
    
    if portfolio_value.empty:
        st.warning(f"No price data available for {selected_asset}")
        return
    
    # Calculate metrics
    returns = calculate_returns(portfolio_value[selected_asset])
    volatility = calculate_volatility(returns)
    sharpe_ratio = calculate_sharpe_ratio(returns)
    max_drawdown = calculate_max_drawdown(portfolio_value[selected_asset])
    best_day, worst_day = calculate_best_worst_day(returns)
    
    # Display metrics
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Volatility", f"{volatility:.2f}%")
        st.metric("Sharpe Ratio", f"{sharpe_ratio:.2f}")
    with col2:
        st.metric("Max Drawdown", f"{max_drawdown:.2f}%")
        st.metric("Best Day", f"{best_day:.2f}%")
    with col3:
        st.metric("Worst Day", f"{worst_day:.2f}%")
    
    # Create price chart
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, 
                       vertical_spacing=0.03, subplot_titles=('Price', 'Volume'),
                       row_heights=[0.7, 0.3])
    
    # Add price line
    fig.add_trace(
        go.Scatter(x=portfolio_value.index, y=portfolio_value[selected_asset],
                  name='Price', line=dict(color='blue')),
        row=1, col=1
    )
    
    # Add volume bars
    fig.add_trace(
        go.Bar(x=asset_transactions['timestamp'], y=asset_transactions['amount'],
               name='Volume', marker_color='gray'),
        row=2, col=1
    )
    
    # Update layout
    fig.update_layout(
        title=f"{selected_asset} Price and Volume",
        xaxis_title="Date",
        yaxis_title="Price",
        height=800,
        showlegend=True
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # Display transaction history
    st.subheader("Transaction History")
    st.dataframe(asset_transactions, hide_index=True, use_container_width=True)
    
    # Display holdings over time
    st.subheader("Holdings Over Time")
    holdings = asset_transactions['amount'].cumsum()
    holdings_chart = go.Figure()
    holdings_chart.add_trace(
        go.Scatter(x=asset_transactions['timestamp'], y=holdings,
                  name='Holdings', line=dict(color='green'))
    )
    holdings_chart.update_layout(
        title=f"{selected_asset} Holdings Over Time",
        xaxis_title="Date",
        yaxis_title="Amount",
        height=400
    )
    st.plotly_chart(holdings_chart, use_container_width=True)

def main():
    """Main function for the Asset Analysis page"""
    st.title("Asset Analysis")
    
    # Initialize session state for transaction selection if not already done
    if 'selected_transaction_id' not in st.session_state:
        st.session_state.selected_transaction_id = None
    
    # Create a container for the portfolio reporter
    if 'portfolio_reporter' not in st.session_state:
        st.session_state.portfolio_reporter = None
    
    # Load data first
    transactions = load_data()
    if transactions is None:
        st.error("Failed to load transaction data.")
        return
    
    # Try to load the portfolio reporter
    try:
        if st.session_state.portfolio_reporter is None:
            # Pass transactions to the constructor
            reporter = PortfolioReporting(transactions)
            st.session_state.portfolio_reporter = reporter
        else:
            reporter = st.session_state.portfolio_reporter
    except Exception as e:
        st.error(f"Error loading portfolio data: {str(e)}")
        return
    
    # Set up two tabs: Price History and Transaction Analysis
    tab1, tab2 = st.tabs(["Price History", "Transaction Analysis"])
    
    # Sidebar for asset selection
    with st.sidebar:
        st.header("Asset Selection")
        
        # Get unique assets from transactions
        unique_assets = sorted(reporter.transactions['asset'].unique())
        
        if not unique_assets:
            st.warning("No assets found. Please upload transaction data first.")
            return
        
        # Asset selection in sidebar applies to both tabs
        asset_symbol = st.selectbox("Select Asset", unique_assets)
        
        if not asset_symbol:
            st.warning("Please select an asset from the sidebar.")
            return
    
    # Get asset transactions and price data
    transactions = reporter.transactions
    
    # Filter for selected asset
    asset_transactions = transactions[transactions['asset'] == asset_symbol].copy()
    
    if asset_transactions.empty:
        st.warning(f"No transactions found for {asset_symbol}.")
        return
    
    # Load price data for the selected asset
    price_data = reporter.get_price_data(asset_symbol)
    
    with tab1:
        # Display price chart
        display_price_chart(reporter, asset_symbol, price_data, transactions)
    
    with tab2:
        st.subheader("Transaction Analysis")
        
        # Get unique years and transaction types for filters
        transaction_years = sorted(asset_transactions['timestamp'].dt.year.astype(str).unique(), reverse=True)
        transaction_types = sorted(asset_transactions['type'].unique())
        
        # Format transaction types for display
        display_types = [tx_type.replace('_', ' ').title() for tx_type in transaction_types]
        
        # Create a mapping from display name to actual type
        type_mapping = dict(zip(display_types, transaction_types))
        
        # Layout for filters - side by side with improved UI
        col1, col2 = st.columns(2)
        
        with col1:
            # Year filter with dropdown UI
            st.write("**Filter by Year:**")
            year_expander = st.expander("Select Years", expanded=False)
            with year_expander:
                selected_years = ["All Years"]
                all_years = st.checkbox("All Years", value=True, key="all_years_checkbox")
                
                if all_years:
                    selected_years = ["All Years"]
                else:
                    year_options = []
                    for year in transaction_years:
                        year_selected = st.checkbox(year, key=f"year_{year}")
                        if year_selected:
                            year_options.append(year)
                    
                    if year_options:
                        selected_years = year_options
                    else:
                        selected_years = ["All Years"]
                
                # Quick select buttons
                st.write("Quick Select:")
                year_cols = st.columns(3)
                with year_cols[0]:
                    if st.button("Last Year", key="last_year_btn"):
                        selected_years = [str(datetime.now().year - 1)]
                with year_cols[1]:
                    if st.button("This Year", key="this_year_btn"):
                        selected_years = [str(datetime.now().year)]
                with year_cols[2]:
                    if st.button("All Years", key="all_years_btn"):
                        selected_years = ["All Years"]
        
        with col2:
            # Transaction type filter with dropdown UI
            st.write("**Filter by Type:**")
            type_expander = st.expander("Select Transaction Types", expanded=False)
            with type_expander:
                selected_types_display = ["All Types"]
                all_types = st.checkbox("All Types", value=True, key="all_types_checkbox")
                
                if all_types:
                    selected_types_display = ["All Types"]
                else:
                    type_options = []
                    for type_display in display_types:
                        type_selected = st.checkbox(type_display, key=f"type_{type_display}")
                        if type_selected:
                            type_options.append(type_display)
                    
                    if type_options:
                        selected_types_display = type_options
                    else:
                        selected_types_display = ["All Types"]
                
                # Quick select buttons
                st.write("Quick Select:")
                type_cols = st.columns(4)
                with type_cols[0]:
                    if st.button("Buy Only", key="buy_only_btn"):
                        selected_types_display = ["Buy"]
                with type_cols[1]:
                    if st.button("Sell Only", key="sell_only_btn"):
                        selected_types_display = ["Sell"]
                with type_cols[2]:
                    if st.button("Transfers Only", key="transfers_only_btn"):
                        selected_types_display = ["Transfer In", "Transfer Out"]
                with type_cols[3]:
                    if st.button("All Types", key="all_types_btn"):
                        selected_types_display = ["All Types"]
        
        # Map selected display types back to actual types for filtering
        if "All Types" in selected_types_display:
            selected_types = None
        else:
            selected_types = [type_mapping[t] for t in selected_types_display]
        
        # Selected filters display
        st.write("**Active Filters:**")
        st.write(f"Years: {', '.join(selected_years)}")
        st.write(f"Types: {', '.join(selected_types_display)}")
        
        # Reset filters button
        if st.button("Reset Filters"):
            selected_years = ["All Years"]
            selected_types_display = ["All Types"]
            selected_types = None
        
        # Display filtered transaction history
        filtered_transactions = display_transaction_history(
            reporter, 
            asset_symbol, 
            selected_years, 
            selected_types
        )
        
        # Display transaction statistics based on filtered data
        display_transaction_statistics(reporter, asset_symbol, filtered_transactions)

    # Display asset analysis
    display_asset_analysis(transactions)

if __name__ == "__main__":
    main() 