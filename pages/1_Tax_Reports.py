import streamlit as st

# Configuration must be the first Streamlit command
st.set_page_config(
    page_title="Tax Reports",
    page_icon="📑",
    layout="wide"
)

import pandas as pd
from datetime import datetime
from reporting import PortfolioReporting
from menu import render_navigation

# Render the custom navigation menu
render_navigation()

def format_date(timestamp):
    """Convert timestamp to YYYY-MM-DD format"""
    return pd.to_datetime(timestamp).strftime('%Y-%m-%d')

def display_tax_reports():
    st.title("Tax Reports")
    
    # Define stablecoins set at the top level
    stablecoins = {'USD', 'USDC', 'USDT', 'DAI'}
    
    # Load data
    try:
        transactions = pd.read_csv("output/transactions_normalized.csv", parse_dates=["timestamp"])
    except Exception as e:
        st.error("Error loading transactions: " + str(e))
        return
        
    # Initialize portfolio reporting
    reporter = PortfolioReporting(transactions)
    
    # Tax year selection
    current_year = datetime.now().year
    tax_year = st.selectbox("Select Tax Year", 
                           options=range(current_year - 2, current_year + 1),
                           index=1)
    
    try:
        tax_lots, summary = reporter.generate_tax_report(tax_year)
        if not tax_lots.empty:
            # Asset filter
            unique_assets = sorted(tax_lots['asset'].unique())
            selected_asset = st.selectbox(
                "Filter by Asset",
                options=["All Assets"] + unique_assets,
                index=0
            )
            
            # Filter tax lots if an asset is selected
            if selected_asset != "All Assets":
                tax_lots = tax_lots[tax_lots['asset'] == selected_asset]
            
            # Display sales history
            st.subheader("Sales History")
            
            try:
                # Filter transactions for the selected tax year and asset
                sell_transactions = transactions[
                    (transactions['timestamp'].dt.year == tax_year) &
                    (transactions['type'] == 'sell') &
                    (~transactions['asset'].isin(stablecoins))  # Exclude stablecoins
                ]
                
                if selected_asset != "All Assets":
                    sell_transactions = sell_transactions[sell_transactions['asset'] == selected_asset]
                
                if not sell_transactions.empty:
                    # Get the proceeds data from tax lots for these sell transactions
                    sell_proceeds = tax_lots[['disposal_date', 'proceeds', 'cost_basis', 'gain_loss']].copy()
                    # Convert disposal_date to timestamp and ensure it's timezone-naive
                    sell_proceeds['timestamp'] = pd.to_datetime(sell_proceeds['disposal_date']).dt.tz_localize(None)
                    
                    # Ensure sell_transactions timestamp is timezone-naive
                    display_sells = sell_transactions.copy()
                    display_sells['timestamp'] = display_sells['timestamp'].dt.tz_localize(None)
                    
                    # Format display timestamp after the merge
                    display_sells['display_date'] = display_sells['timestamp'].apply(format_date)
                    
                    # Ensure numeric columns before any calculations
                    numeric_columns = ['quantity', 'price', 'fees', 'subtotal']
                    for col in numeric_columns:
                        if col in display_sells.columns:
                            display_sells[col] = pd.to_numeric(display_sells[col], errors='coerce')
                            # Replace any NaN values with 0
                            display_sells[col] = display_sells[col].fillna(0)

                    # Ensure quantity is numeric and handle NaN values
                    display_sells['quantity'] = pd.to_numeric(display_sells['quantity'], errors='coerce').fillna(0)
                    display_sells['quantity'] = display_sells['quantity'].abs().round(8)  # Make quantity positive
                    display_sells['price'] = display_sells['price'].round(4)
                    
                    # Use values directly from source data
                    display_sells['subtotal'] = display_sells['subtotal'].round(2)  # Use subtotal from source
                    display_sells['fees'] = pd.to_numeric(display_sells['fees'], errors='coerce').fillna(0).abs().round(2)  # Make fees positive
                    display_sells['net_proceeds'] = (display_sells['subtotal'] - display_sells['fees']).round(2)
                    
                    # Debug print each transaction
                    print("\nDebug: Detailed Transaction Breakdown:")
                    for _, row in display_sells.iterrows():
                        print(f"{row['asset']}: Date={row['display_date']}, Subtotal=${row['subtotal']:.2f}, Fees=${row['fees']:.2f}, Net=${row['net_proceeds']:.2f}")
                    print(f"Total Net Proceeds: ${display_sells['net_proceeds'].sum():.2f}")
                    
                    # Get tax lot information for each sale
                    tax_lot_info = {}
                    for _, row in display_sells.iterrows():
                        # Find matching tax lots for this sale
                        matching_lots = tax_lots[
                            (tax_lots['disposal_date'].dt.tz_localize(None) == row['timestamp']) &
                            (tax_lots['asset'] == row['asset'])
                        ]
                        if not matching_lots.empty:
                            tax_lot_info[row['timestamp']] = {
                                'cost_basis': matching_lots['cost_basis'].sum(),
                                'gain_loss': matching_lots['gain_loss'].sum(),
                                'acquisition_types': ', '.join(matching_lots['acquisition_type'].unique())
                            }
                    
                    # Add tax lot information to display_sells
                    display_sells['cost_basis'] = display_sells['timestamp'].map(
                        lambda x: tax_lot_info.get(x, {}).get('cost_basis', 0)
                    ).round(2)
                    
                    display_sells['gain_loss'] = display_sells['timestamp'].map(
                        lambda x: tax_lot_info.get(x, {}).get('gain_loss', 0)
                    ).round(2)
                    
                    display_sells['source'] = display_sells['timestamp'].map(
                        lambda x: tax_lot_info.get(x, {}).get('acquisition_types', 'unknown')
                    )
                    
                    # Add holding period days from tax lots
                    display_sells['holding_period_days'] = display_sells['timestamp'].map(
                        lambda x: tax_lots[
                            (tax_lots['disposal_date'].dt.tz_localize(None) == x)
                        ]['holding_period_days'].iloc[0] if not tax_lots[
                            (tax_lots['disposal_date'].dt.tz_localize(None) == x)
                        ].empty else 0
                    )
                    
                    # Format display date
                    display_sells['display_date'] = display_sells['timestamp'].apply(format_date)
                    
                    # Select and reorder columns
                    display_columns = [
                        'display_date', 'type', 'asset', 'quantity', 'price', 
                        'subtotal', 'fees', 'net_proceeds', 'cost_basis', 'gain_loss', 'source', 'holding_period_days'
                    ]
                    
                    # Add optional columns if they exist
                    if 'currency' in display_sells.columns:
                        display_columns.append('currency')
                    if 'institution' in display_sells.columns:
                        display_columns.append('institution')
                    
                    display_sells = display_sells[display_columns]
                    
                    # Create column config with required columns
                    column_config = {
                        "display_date": "Date",
                        "type": "Type",
                        "asset": "Asset",
                        "quantity": st.column_config.NumberColumn("Quantity", format="%.8f"),
                        "price": st.column_config.NumberColumn("Price", format="$%.4f"),
                        "subtotal": st.column_config.NumberColumn("Subtotal", format="$%.2f"),
                        "fees": st.column_config.NumberColumn("Fees", format="$%.2f"),
                        "net_proceeds": st.column_config.NumberColumn("Net Proceeds", format="$%.2f"),
                        "cost_basis": st.column_config.NumberColumn("Cost Basis", format="$%.2f"),
                        "gain_loss": st.column_config.NumberColumn("Gain/Loss", format="$%.2f"),
                        "source": "Source Lots",
                        "holding_period_days": "Holding Period (Days)"
                    }
                    
                    # Add optional columns to config if they exist
                    if 'currency' in display_sells.columns:
                        column_config["currency"] = "Currency"
                    if 'institution' in display_sells.columns:
                        column_config["institution"] = "Exchange"
                    
                    # Calculate summary metrics from display_sells
                    summary = {
                        'net_proceeds': float(display_sells['net_proceeds'].sum()),
                        'total_gain_loss': float(display_sells['gain_loss'].sum()),
                        'short_term_gain_loss': float(display_sells[display_sells['holding_period_days'] <= 365]['gain_loss'].sum()),
                        'long_term_gain_loss': float(display_sells[display_sells['holding_period_days'] > 365]['gain_loss'].sum())
                    }
                    
                    # Display summary metrics at the top
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("Net Proceeds", f"${summary['net_proceeds']:,.2f}")
                    with col2:
                        st.metric("Total Gain/Loss", f"${summary['total_gain_loss']:,.2f}")
                    with col3:
                        st.metric("Short-term G/L", f"${summary['short_term_gain_loss']:,.2f}")
                    with col4:
                        st.metric("Long-term G/L", f"${summary['long_term_gain_loss']:,.2f}")
                    
                    # Add note about stablecoins if relevant
                    if any(asset in stablecoins for asset in tax_lots['asset'].unique()):
                        st.info("Note: Stablecoin transactions (USD, USDC, USDT, DAI) are excluded from tax calculations as they are not taxable events.")
                    
                    st.dataframe(
                        display_sells,
                        column_config=column_config,
                        hide_index=True
                    )
                    
                    # Add a note about the values
                    st.info("Note: Values shown are from Coinbase transaction data. Subtotal represents the total value before fees, and Net Proceeds represents the actual amount received after fees.")
                else:
                    st.info(f"No sales found for {tax_year}")
            except Exception as e:
                st.error(f"Error displaying sales history: {str(e)}")
            
            try:
                # Format dates in tax lots
                tax_lots['acquisition_date'] = tax_lots['acquisition_date'].apply(format_date)
                tax_lots['disposal_date'] = tax_lots['disposal_date'].apply(format_date)
                
                # Round numeric columns - using only columns that exist in the DataFrame
                numeric_cols = ['quantity', 'cost_basis', 'proceeds', 'gain_loss']
                tax_lots[numeric_cols] = tax_lots[numeric_cols].round(8)
                
                # Display tax lots
                st.subheader("Tax Lots")
                st.info("Cost basis calculated using FIFO (First In, First Out) method")
                st.dataframe(
                    tax_lots,
                    column_config={
                        "asset": "Asset",
                        "quantity": st.column_config.NumberColumn("Quantity", format="%.8f"),
                        "acquisition_date": "Acquisition Date",
                        "disposal_date": "Disposal Date",
                        "cost_basis": st.column_config.NumberColumn("Cost Basis", format="$%.2f"),
                        "proceeds": st.column_config.NumberColumn("Proceeds", format="$%.2f"),
                        "gain_loss": st.column_config.NumberColumn("Gain/Loss", format="$%.2f"),
                        "holding_period_days": "Holding Period (Days)"
                    },
                    hide_index=True
                )
                
                # Export button
                csv = tax_lots.to_csv(index=False)
                st.download_button(
                    label="Download Tax Report",
                    data=csv,
                    file_name=f'tax_report_{tax_year}_{selected_asset.lower().replace(" ", "_")}.csv',
                    mime='text/csv'
                )
            except Exception as e:
                st.error(f"Error displaying tax lots: {str(e)}")
        else:
            st.info(f"No tax lots found for {tax_year}")
    except Exception as e:
        st.error(f"Error generating tax report: {str(e)}")

if __name__ == "__main__":
    display_tax_reports() 