import streamlit as st
import pandas as pd
from datetime import datetime
from reporting import PortfolioReporting

# Must be the first Streamlit command
st.set_page_config(
    page_title="Tax Reports",
    page_icon="🧾",
    layout="wide",
    initial_sidebar_state="collapsed",
    menu_items={
        'Get Help': None,
        'Report a bug': None,
        'About': "# Portfolio Analytics\nA tool for analyzing cryptocurrency portfolio performance and generating tax reports."
    }
)

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

def display_tax_report(reporter: PortfolioReporting, year: int, selected_symbol: str = "All Assets"):
    """Display tax report for the specified year"""
    try:
        tax_lots, summary = reporter.generate_tax_report(year)
        
        if tax_lots.empty:
            st.info(f"No taxable transactions found for {year}.")
            return
            
        # Filter by selected symbol if not "All Assets"
        if selected_symbol != "All Assets":
            tax_lots = tax_lots[tax_lots["asset"] == selected_symbol]
            if tax_lots.empty:
                st.info(f"No taxable transactions found for {selected_symbol} in {year}.")
                return
        
        # Display summary metrics
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Net Proceeds", f"${summary['net_proceeds']:,.2f}")
        with col2:
            st.metric("Total Gain/Loss", f"${summary['total_gain_loss']:,.2f}")
        with col3:
            st.metric("Short-term G/L", f"${summary['short_term_gain_loss']:,.2f}")
        with col4:
            st.metric("Long-term G/L", f"${summary['long_term_gain_loss']:,.2f}")
            
        # Display Sales History section first
        st.subheader("Sales History")
        sales_df = reporter.show_sell_transactions_with_lots()
        
        if not sales_df.empty:
            # Filter sales for the selected year and symbol
            sales_df['date'] = pd.to_datetime(sales_df['date'])
            year_sales = sales_df[sales_df['date'].dt.year == year]
            
            if selected_symbol != "All Assets":
                year_sales = year_sales[year_sales['asset'] == selected_symbol]
            
            if not year_sales.empty:
                # Convert date back to string format (YYYY-MM-DD)
                year_sales['date'] = year_sales['date'].dt.strftime("%Y-%m-%d")
                
                # Rename columns for display
                sales_display_names = {
                    'date': 'Date',
                    'type': 'Type',
                    'asset': 'Asset',
                    'quantity': 'Quantity',
                    'price': 'Price',
                    'subtotal': 'Subtotal',
                    'fees': 'Fees',
                    'net_proceeds': 'Net Proceeds',
                    'cost_basis': 'Cost Basis',
                    'net_profit': 'Net Profit'
                }
                
                # Select only the columns we want to display
                display_columns = ['date', 'type', 'asset', 'quantity', 'price', 'subtotal', 'fees', 'net_proceeds', 'cost_basis', 'net_profit']
                year_sales = year_sales[display_columns]
                
                year_sales.columns = [sales_display_names[col] for col in year_sales.columns]
                
                # Format dollar columns
                dollar_columns = ['Price', 'Subtotal', 'Fees', 'Net Proceeds', 'Cost Basis', 'Net Profit']
                for col in dollar_columns:
                    year_sales[col] = year_sales[col].apply(lambda x: f"${x:,.2f}")
                
                st.dataframe(year_sales, hide_index=True, use_container_width=True)
            else:
                st.info(f"No sales found for {selected_symbol} in {year}")
        else:
            st.info("No sales history available")
            
        # Display detailed tax lots
        st.subheader("Detailed Tax Lots")
        
        # Add download button for CSV
        csv = tax_lots.to_csv(index=False)
        st.download_button(
            label="Download Tax Report (CSV)",
            data=csv,
            file_name=f"tax_report_{year}.csv",
            mime="text/csv"
        )
        
        # Display paginated tax lots
        rows_per_page = 20
        total_pages = (len(tax_lots) + rows_per_page - 1) // rows_per_page
        page = st.number_input("Page", min_value=1, max_value=total_pages, value=1) - 1
        
        start_idx = page * rows_per_page
        end_idx = start_idx + rows_per_page
        
        # Updated display columns to match actual DataFrame columns
        display_cols = [
            'asset', 'quantity', 'acquisition_date', 'disposal_date',
            'proceeds', 'fees', 'cost_basis', 'gain_loss', 'holding_period_days'
        ]
        
        # Rename columns for display
        display_names = {
            'asset': 'Asset',
            'quantity': 'Quantity',
            'acquisition_date': 'Acquisition Date',
            'disposal_date': 'Disposal Date',
            'proceeds': 'Proceeds',
            'fees': 'Fees',
            'cost_basis': 'Cost Basis',
            'gain_loss': 'Gain/Loss',
            'holding_period_days': 'Holding Period (Days)'
        }
        
        display_df = tax_lots[display_cols].copy()
        display_df.columns = [display_names[col] for col in display_cols]
        
        # Format dollar columns
        dollar_columns = ['Proceeds', 'Fees', 'Cost Basis', 'Gain/Loss']
        for col in dollar_columns:
            display_df[col] = display_df[col].apply(lambda x: f"${x:,.2f}")
        
        st.dataframe(
            display_df.iloc[start_idx:end_idx],
            hide_index=True,
            use_container_width=True
        )
        
    except Exception as e:
        st.error(f"Error generating tax report: {str(e)}")

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
    default_year = current_year - 1  # Most recently completed year
    
    year = st.selectbox(
        "Select Tax Year",
        available_years,
        index=0  # First year (most recent) will be selected by default
    )
    
    # Get sales transactions for the selected year
    sales_df = reporter.show_sell_transactions_with_lots()
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
    
    # Display tax report
    display_tax_report(reporter, year, selected_symbol)

if __name__ == "__main__":
    main() 