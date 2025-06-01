import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, date, timedelta
import time
import logging
from typing import Dict, List, Optional, Tuple
import asyncio
from concurrent.futures import ThreadPoolExecutor
import warnings
import psutil
import os
warnings.filterwarnings('ignore')

# Import our modules
from app.analytics.portfolio import (
    compute_portfolio_time_series,
    compute_portfolio_time_series_with_external_prices,
    calculate_cost_basis_fifo,
    calculate_cost_basis_avg
)
from app.services.price_service import PriceService
from app.db.session import get_db
from app.db.base import Asset, PriceData
from app.analytics.returns import daily_returns, cumulative_returns, volatility, sharpe_ratio, maximum_drawdown

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Page configuration
st.set_page_config(
    page_title="Portfolio Analytics Pro",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        'Get Help': 'https://github.com/your-repo/portfolio-analytics',
        'Report a bug': "https://github.com/your-repo/portfolio-analytics/issues",
        'About': "# Portfolio Analytics Pro\nProfessional-grade portfolio tracking and analysis."
    }
)

# Custom CSS for modern styling
st.markdown("""
<style>
    /* Main theme colors */
    :root {
        --primary-color: #1f77b4;
        --secondary-color: #ff7f0e;
        --success-color: #2ca02c;
        --danger-color: #d62728;
        --warning-color: #ff7f0e;
        --info-color: #17a2b8;
        --light-bg: #f8f9fa;
        --dark-bg: #343a40;
    }
    
    /* Hide Streamlit branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    /* Custom metric cards */
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1.5rem;
        border-radius: 10px;
        color: white;
        margin: 0.5rem 0;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        transition: transform 0.2s ease;
    }
    
    .metric-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 12px rgba(0, 0, 0, 0.15);
    }
    
    .metric-value {
        font-size: 2rem;
        font-weight: bold;
        margin: 0;
    }
    
    .metric-label {
        font-size: 0.9rem;
        opacity: 0.9;
        margin: 0;
    }
    
    /* Performance indicator */
    .performance-indicator {
        position: fixed;
        top: 10px;
        right: 10px;
        background: rgba(0, 0, 0, 0.8);
        color: white;
        padding: 5px 10px;
        border-radius: 5px;
        font-size: 0.8rem;
        z-index: 1000;
    }
    
    /* Loading spinner */
    .loading-spinner {
        display: inline-block;
        width: 20px;
        height: 20px;
        border: 3px solid #f3f3f3;
        border-top: 3px solid var(--primary-color);
        border-radius: 50%;
        animation: spin 1s linear infinite;
    }
    
    @keyframes spin {
        0% { transform: rotate(0deg); }
        100% { transform: rotate(360deg); }
    }
    
    /* Sidebar styling */
    .css-1d391kg {
        background: linear-gradient(180deg, #667eea 0%, #764ba2 100%);
    }
    
    /* Chart containers */
    .chart-container {
        background: white;
        border-radius: 10px;
        padding: 1rem;
        margin: 1rem 0;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
    }
    
    /* Status indicators */
    .status-success { color: var(--success-color); }
    .status-warning { color: var(--warning-color); }
    .status-danger { color: var(--danger-color); }
    .status-info { color: var(--info-color); }
</style>
""", unsafe_allow_html=True)

class PerformanceMonitor:
    """Monitor and display performance metrics"""
    
    def __init__(self):
        self.start_time = time.time()
        self.metrics = {}
    
    def start_timer(self, operation: str):
        self.metrics[operation] = {'start': time.time()}
    
    def end_timer(self, operation: str):
        if operation in self.metrics:
            self.metrics[operation]['duration'] = time.time() - self.metrics[operation]['start']
    
    def get_total_time(self) -> float:
        return time.time() - self.start_time
    
    def display_metrics(self):
        """Display performance metrics in sidebar"""
        with st.sidebar:
            st.markdown("### ⚡ Performance")
            total_time = self.get_total_time()
            
            if total_time < 2:
                status = "🟢 Excellent"
            elif total_time < 5:
                status = "🟡 Good"
            else:
                status = "🔴 Slow"
            
            st.markdown(f"**Load Time:** {total_time:.2f}s {status}")
            
            if self.metrics:
                with st.expander("Detailed Metrics"):
                    for op, data in self.metrics.items():
                        if 'duration' in data:
                            st.text(f"{op}: {data['duration']:.3f}s")

# Initialize performance monitor
perf_monitor = PerformanceMonitor()

@st.cache_data(ttl=300, show_spinner=False)
def load_normalized_transactions() -> Optional[pd.DataFrame]:
    """Load normalized transaction data with enhanced error handling."""
    try:
        transactions = pd.read_csv("output/transactions_normalized.csv", parse_dates=["timestamp"])
        
        # Add compatibility layer for amount/quantity column
        if 'amount' not in transactions.columns and 'quantity' in transactions.columns:
            transactions['amount'] = transactions['quantity']
            st.info("ℹ️ Using 'quantity' column as 'amount' for compatibility")
        elif 'quantity' not in transactions.columns and 'amount' in transactions.columns:
            transactions['quantity'] = transactions['amount']
        
        # Validate required columns
        required_columns = ['timestamp', 'type', 'asset', 'amount', 'price']
        missing_columns = [col for col in required_columns if col not in transactions.columns]
        if missing_columns:
            st.error(f"❌ Missing required columns: {missing_columns}")
            return None
        
        # Data cleaning and validation
        transactions = transactions.dropna(subset=['asset', 'amount'])
        transactions['timestamp'] = pd.to_datetime(transactions['timestamp'])
        
        # Convert numeric columns to float for calculations
        numeric_columns = ['amount', 'price', 'fees']
        for col in numeric_columns:
            if col in transactions.columns:
                transactions[col] = pd.to_numeric(transactions[col], errors='coerce').fillna(0)
        
        return transactions
        
    except FileNotFoundError:
        st.error("❌ Normalized transaction data not found. Please run the data pipeline first.")
        st.code("PYTHONPATH=$(pwd) python -c \"from app.ingestion.loader import process_transactions; result_df = process_transactions('data/transaction_history', 'config/schema_mapping.yaml'); result_df.to_csv('output/transactions_normalized.csv', index=False); print(f'Processed {len(result_df)} transactions')\"")
        return None
    except Exception as e:
        st.error(f"❌ Error loading transaction data: {str(e)}")
        return None

@st.cache_data(ttl=600, show_spinner=False)
def compute_portfolio_metrics(transactions: pd.DataFrame) -> Dict:
    """Compute comprehensive portfolio metrics using external price data."""
    try:
        # Use external price data for portfolio calculation
        portfolio_ts = compute_portfolio_time_series_with_external_prices(transactions)
        
        if portfolio_ts.empty or 'total' not in portfolio_ts.columns:
            return {
                'current_value': 0.0,
                'total_return': 0.0,
                'total_return_pct': 0.0,
                'annualized_return': 0.0,
                'volatility': 0.0,
                'sharpe_ratio': 0.0,
                'max_drawdown': 0.0,
                'best_day': 0.0,
                'worst_day': 0.0,
                'portfolio_ts': pd.DataFrame(),
                'returns': pd.Series(),
                'drawdown': pd.Series()
            }
        
        # Convert to float to avoid Decimal issues
        total_values = portfolio_ts['total'].astype(float)
        
        # Calculate returns
        returns = daily_returns(total_values)
        
        # Calculate drawdown series for charting
        peak_values = total_values.expanding().max()
        drawdown_series = (total_values / peak_values - 1) * 100  # Convert to percentage
        
        # Current portfolio value
        current_value = float(total_values.iloc[-1]) if len(total_values) > 0 else 0.0
        initial_value = float(total_values.iloc[0]) if len(total_values) > 0 else 1.0
        
        # Total return
        total_return = current_value - initial_value
        total_return_pct = (current_value / initial_value - 1) * 100 if initial_value != 0 else 0.0
        
        # Annualized return
        days = len(total_values)
        years = days / 365.25 if days > 0 else 1
        annualized_return = ((current_value / initial_value) ** (1/years) - 1) * 100 if initial_value != 0 and years > 0 else 0.0
        
        # Risk metrics
        vol = volatility(returns, annualized=True) if len(returns) > 1 else 0.0
        sharpe = sharpe_ratio(returns) if len(returns) > 1 else 0.0
        
        # Fix: Extract only the drawdown value from the tuple
        if len(total_values) > 1:
            max_dd_tuple = maximum_drawdown(total_values)
            max_dd = float(max_dd_tuple[0]) * 100  # Convert to percentage and extract first element
        else:
            max_dd = 0.0
        
        # Best and worst days
        best_day = float(returns.max()) * 100 if len(returns) > 0 else 0.0
        worst_day = float(returns.min()) * 100 if len(returns) > 0 else 0.0
        
        return {
            'current_value': current_value,
            'total_return': total_return,
            'total_return_pct': total_return_pct,
            'annualized_return': annualized_return,
            'volatility': vol,
            'sharpe_ratio': sharpe,
            'max_drawdown': max_dd,
            'best_day': best_day,
            'worst_day': worst_day,
            'portfolio_ts': portfolio_ts,
            'returns': returns,
            'drawdown': drawdown_series
        }
        
    except Exception as e:
        st.error(f"❌ Error computing portfolio metrics: {str(e)}")
        return {
            'current_value': 0.0,
            'total_return': 0.0,
            'total_return_pct': 0.0,
            'annualized_return': 0.0,
            'volatility': 0.0,
            'sharpe_ratio': 0.0,
            'max_drawdown': 0.0,
            'best_day': 0.0,
            'worst_day': 0.0,
            'portfolio_ts': pd.DataFrame(),
            'returns': pd.Series(),
            'drawdown': pd.Series()
        }

@st.cache_data(ttl=300, show_spinner=False)
def get_asset_allocation(transactions: pd.DataFrame) -> pd.DataFrame:
    """Calculate current asset allocation with caching"""
    perf_monitor.start_timer("get_asset_allocation")
    
    try:
        portfolio_ts = compute_portfolio_time_series_with_external_prices(transactions)
        if portfolio_ts.empty:
            return pd.DataFrame()
        
        # Get latest values
        latest_values = portfolio_ts.iloc[-1].drop('total')
        total_value = latest_values.sum()
        
        if total_value == 0:
            return pd.DataFrame()
        
        allocation = pd.DataFrame({
            'Asset': latest_values.index,
            'Value': latest_values.values,
            'Allocation': (latest_values / total_value * 100).round(2)
        }).sort_values('Value', ascending=False)
        
        perf_monitor.end_timer("get_asset_allocation")
        return allocation
        
    except Exception as e:
        logger.error(f"Error calculating asset allocation: {e}")
        return pd.DataFrame()

def create_metric_card(title: str, value: str, delta: Optional[str] = None, delta_color: str = "normal"):
    """Create a custom metric card with styling"""
    delta_html = ""
    if delta:
        color_class = f"status-{delta_color}" if delta_color != "normal" else ""
        delta_html = f'<p class="metric-delta {color_class}">{delta}</p>'
    
    st.markdown(f"""
    <div class="metric-card">
        <p class="metric-label">{title}</p>
        <p class="metric-value">{value}</p>
        {delta_html}
    </div>
    """, unsafe_allow_html=True)

def create_portfolio_overview_chart(portfolio_ts: pd.DataFrame, returns: pd.Series, drawdown: pd.Series):
    """Create comprehensive portfolio overview chart"""
    
    # Create subplots
    fig = make_subplots(
        rows=3, cols=1,
        subplot_titles=('Portfolio Value', 'Daily Returns', 'Drawdown'),
        vertical_spacing=0.08,
        row_heights=[0.5, 0.25, 0.25]
    )
    
    # Portfolio value
    fig.add_trace(
        go.Scatter(
            x=portfolio_ts.index,
            y=portfolio_ts['total'],
            mode='lines',
            name='Portfolio Value',
            line=dict(color='#1f77b4', width=2),
            fill='tonexty',
            fillcolor='rgba(31, 119, 180, 0.1)'
        ),
        row=1, col=1
    )
    
    # Daily returns
    colors = ['red' if x < 0 else 'green' for x in returns]
    fig.add_trace(
        go.Bar(
            x=returns.index,
            y=returns * 100,
            name='Daily Returns (%)',
            marker_color=colors,
            opacity=0.7
        ),
        row=2, col=1
    )
    
    # Drawdown
    fig.add_trace(
        go.Scatter(
            x=drawdown.index,
            y=drawdown,
            mode='lines',
            name='Drawdown (%)',
            line=dict(color='red', width=1),
            fill='tonexty',
            fillcolor='rgba(255, 0, 0, 0.1)'
        ),
        row=3, col=1
    )
    
    # Update layout
    fig.update_layout(
        height=800,
        showlegend=False,
        title_text="Portfolio Performance Overview",
        title_x=0.5,
        title_font_size=20
    )
    
    # Update axes
    fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor='rgba(128, 128, 128, 0.2)')
    fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor='rgba(128, 128, 128, 0.2)')
    
    return fig

def create_asset_allocation_chart(allocation: pd.DataFrame):
    """Create interactive asset allocation chart"""
    if allocation.empty:
        return None
    
    # Pie chart
    fig_pie = px.pie(
        allocation,
        values='Value',
        names='Asset',
        title='Asset Allocation by Value',
        color_discrete_sequence=px.colors.qualitative.Set3
    )
    
    fig_pie.update_traces(
        textposition='inside',
        textinfo='percent+label',
        hovertemplate='<b>%{label}</b><br>Value: $%{value:,.2f}<br>Allocation: %{percent}<extra></extra>'
    )
    
    fig_pie.update_layout(
        showlegend=True,
        legend=dict(orientation="v", yanchor="middle", y=0.5, xanchor="left", x=1.01)
    )
    
    return fig_pie

def display_performance_dashboard():
    """Display the main performance dashboard"""
    st.header("📊 Portfolio Performance Dashboard")
    
    # Load and validate normalized data
    transactions = load_normalized_transactions()
    if transactions is None or transactions.empty:
        st.error("❌ No transaction data available. Please run the data pipeline first.")
        st.code("PYTHONPATH=$(pwd) python -c \"from app.ingestion.loader import process_transactions; ...\"")
        return
    
    # Validate required columns
    required_columns = ['timestamp', 'type', 'asset', 'quantity', 'price', 'institution']
    missing_columns = [col for col in required_columns if col not in transactions.columns]
    if missing_columns:
        st.error(f"❌ Missing required columns: {missing_columns}")
        return
    
    # Display basic stats
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Transactions", f"{len(transactions):,}")
    with col2:
        st.metric("Unique Assets", f"{transactions['asset'].nunique()}")
    with col3:
        st.metric("Institutions", f"{transactions['institution'].nunique()}")
    with col4:
        date_range = f"{transactions['timestamp'].min().strftime('%Y-%m-%d')} to {transactions['timestamp'].max().strftime('%Y-%m-%d')}"
        st.metric("Date Range", date_range)
    
    # Compute portfolio metrics with progress indicator
    with st.spinner("🔄 Computing portfolio metrics with historical price data..."):
        metrics = compute_portfolio_metrics(transactions)
    
    # Check if metrics computation was successful
    if 'portfolio_ts' not in metrics or metrics['portfolio_ts'].empty:
        st.warning("⚠️ Portfolio calculation returned no data. This may be due to missing price data.")
        st.info("💡 The system prioritizes historical CSV price data, then falls back to external APIs.")
        return
    
    # Key Performance Indicators
    st.header("📈 Key Performance Indicators")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "Portfolio Value",
            f"${metrics['current_value']:,.2f}",
            f"${metrics['total_return']:,.2f}"
        )
    
    with col2:
        st.metric(
            "Total Return", 
            f"{metrics['total_return_pct']:.2f}%",
            f"{metrics['annualized_return']:.2f}% annualized"
        )
    
    with col3:
        st.metric(
            "Sharpe Ratio",
            f"{metrics['sharpe_ratio']:.2f}",
            f"{metrics['volatility']:.2f}% volatility"
        )
    
    with col4:
        st.metric(
            "Max Drawdown",
            f"{metrics['max_drawdown']:.2f}%",
            f"{metrics['best_day']:.2f}% best day"
        )
    
    # Portfolio overview chart
    st.markdown("### 📈 Portfolio Overview")
    overview_chart = create_portfolio_overview_chart(
        metrics['portfolio_ts'],
        metrics['returns'],
        metrics['drawdown']
    )
    st.plotly_chart(overview_chart, use_container_width=True)
    
    # Asset allocation
    st.markdown("### 🥧 Asset Allocation")
    allocation = get_asset_allocation(transactions)
    
    if not allocation.empty:
        col1, col2 = st.columns([2, 1])
        
        with col1:
            allocation_chart = create_asset_allocation_chart(allocation)
            if allocation_chart:
                st.plotly_chart(allocation_chart, use_container_width=True)
        
        with col2:
            st.markdown("#### Holdings Summary")
            st.dataframe(
                allocation.style.format({
                    'Value': '${:,.2f}',
                    'Allocation': '{:.2f}%'
                }),
                hide_index=True,
                use_container_width=True
            )
    else:
        st.info("ℹ️ No allocation data available")

def display_transaction_analysis():
    """Display transaction analysis page"""
    st.markdown("## 📋 Transaction Analysis")
    
    transactions = load_normalized_transactions()
    if transactions is None:
        return
    
    # Filters
    st.markdown("### 🔍 Filters")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        # Date range filter
        min_date = transactions['timestamp'].min().date()
        max_date = transactions['timestamp'].max().date()
        date_range = st.date_input(
            "Date Range",
            value=(min_date, max_date),
            min_value=min_date,
            max_value=max_date
        )
    
    with col2:
        # Asset filter
        assets = ["All"] + sorted(transactions['asset'].unique().tolist())
        selected_asset = st.selectbox("Asset", assets)
    
    with col3:
        # Transaction type filter
        tx_types = ["All"] + sorted(transactions['type'].unique().tolist())
        selected_type = st.selectbox("Transaction Type", tx_types)
    
    # Apply filters
    filtered_tx = transactions.copy()
    
    if len(date_range) == 2:
        filtered_tx = filtered_tx[
            (filtered_tx['timestamp'].dt.date >= date_range[0]) &
            (filtered_tx['timestamp'].dt.date <= date_range[1])
        ]
    
    if selected_asset != "All":
        filtered_tx = filtered_tx[filtered_tx['asset'] == selected_asset]
    
    if selected_type != "All":
        filtered_tx = filtered_tx[filtered_tx['type'] == selected_type]
    
    # Transaction summary
    st.markdown("### 📊 Transaction Summary")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Transactions", len(filtered_tx))
    
    with col2:
        total_volume = (filtered_tx['quantity'] * filtered_tx['price']).sum()
        st.metric("Total Volume", f"${total_volume:,.2f}")
    
    with col3:
        avg_size = (filtered_tx['quantity'] * filtered_tx['price']).mean()
        st.metric("Avg Transaction Size", f"${avg_size:,.2f}")
    
    with col4:
        total_fees = filtered_tx['fees'].sum()
        st.metric("Total Fees", f"${total_fees:,.2f}")
    
    # Transaction type breakdown
    if not filtered_tx.empty:
        st.markdown("### 📈 Transaction Type Breakdown")
        
        type_summary = filtered_tx.groupby('type').agg({
            'quantity': 'count',
            'price': lambda x: (filtered_tx.loc[x.index, 'quantity'] * x).sum()
        }).round(2)
        type_summary.columns = ['Count', 'Total Value']
        
        fig_types = px.bar(
            type_summary.reset_index(),
            x='type',
            y='Count',
            title='Transactions by Type',
            color='type'
        )
        st.plotly_chart(fig_types, use_container_width=True)
    
    # Transaction table
    st.markdown("### 📋 Transaction Details")
    
    # Add download button
    csv = filtered_tx.to_csv(index=False)
    st.download_button(
        label="📥 Download CSV",
        data=csv,
        file_name=f"transactions_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        mime="text/csv"
    )
    
    # Display table with pagination
    page_size = st.selectbox("Rows per page", [10, 25, 50, 100], index=1)
    
    if not filtered_tx.empty:
        total_pages = len(filtered_tx) // page_size + (1 if len(filtered_tx) % page_size > 0 else 0)
        page = st.selectbox("Page", range(1, total_pages + 1))
        
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        
        st.dataframe(
            filtered_tx.iloc[start_idx:end_idx].style.format({
                'quantity': '{:.6f}',
                'price': '${:.2f}',
                'fees': '${:.2f}'
            }),
            use_container_width=True
        )
    else:
        st.info("ℹ️ No transactions match the selected filters")

def display_tax_reports():
    """Display tax reports page"""
    st.markdown("## 🧾 Tax Reports")
    
    transactions = load_normalized_transactions()
    if transactions is None:
        return
    
    # Year selection
    years = sorted(transactions['timestamp'].dt.year.unique(), reverse=True)
    selected_year = st.selectbox("Tax Year", years)
    
    # Filter transactions for selected year
    year_transactions = transactions[transactions['timestamp'].dt.year == selected_year]
    
    if year_transactions.empty:
        st.warning(f"⚠️ No transactions found for {selected_year}")
        return
    
    # Calculate tax lots
    with st.spinner("🔄 Calculating tax lots..."):
        fifo_lots = calculate_cost_basis_fifo(year_transactions)
        avg_lots = calculate_cost_basis_avg(year_transactions)
    
    # Tax summary
    st.markdown(f"### 📊 Tax Summary for {selected_year}")
    
    tab1, tab2 = st.tabs(["FIFO Method", "Average Cost Method"])
    
    with tab1:
        if not fifo_lots.empty:
            total_gain_loss = fifo_lots['gain_loss'].sum()
            total_proceeds = (fifo_lots['quantity'] * fifo_lots['price']).sum()
            total_cost = (fifo_lots['quantity'] * fifo_lots['cost_basis']).sum()
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Proceeds", f"${total_proceeds:,.2f}")
            with col2:
                st.metric("Total Cost Basis", f"${total_cost:,.2f}")
            with col3:
                color = "normal" if total_gain_loss >= 0 else "inverse"
                st.metric("Total Gain/Loss", f"${total_gain_loss:,.2f}")
            
            st.dataframe(fifo_lots, use_container_width=True)
            
            # Download button
            csv = fifo_lots.to_csv(index=False)
            st.download_button(
                "📥 Download FIFO Report",
                csv,
                f"fifo_tax_report_{selected_year}.csv",
                "text/csv"
            )
        else:
            st.info("ℹ️ No FIFO tax lots available")
    
    with tab2:
        if not avg_lots.empty:
            total_cost_basis = avg_lots['avg_cost_basis'].sum()
            
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Total Cost Basis", f"${total_cost_basis:,.2f}")
            with col2:
                st.metric("Number of Lots", len(avg_lots))
            
            st.dataframe(avg_lots, use_container_width=True)
            
            # Download button
            csv = avg_lots.to_csv(index=False)
            st.download_button(
                "📥 Download Average Cost Report",
                csv,
                f"avg_cost_tax_report_{selected_year}.csv",
                "text/csv"
            )
        else:
            st.info("ℹ️ No average cost tax lots available")

def main():
    """Main application function"""
    
    # App header
    st.markdown("""
    # 📈 Portfolio Analytics Pro
    ### Professional-grade portfolio tracking and analysis
    """)
    
    # Sidebar navigation
    with st.sidebar:
        st.markdown("## 🧭 Navigation")
        
        page = st.radio(
            "Select Page",
            ["📊 Dashboard", "📋 Transactions", "🧾 Tax Reports", "⚙️ Settings"],
            format_func=lambda x: x
        )
        
        st.markdown("---")
        
        # Performance monitor
        perf_monitor.display_metrics()
        
        st.markdown("---")
        
        # Quick stats
        transactions = load_normalized_transactions()
        if transactions is not None:
            st.markdown("### 📊 Quick Stats")
            st.metric("Total Transactions", len(transactions))
            st.metric("Assets Tracked", transactions['asset'].nunique())
            st.metric("Date Range", f"{transactions['timestamp'].min().strftime('%Y-%m-%d')} to {transactions['timestamp'].max().strftime('%Y-%m-%d')}")
    
    # Route to appropriate page
    if page == "📊 Dashboard":
        display_performance_dashboard()
    elif page == "📋 Transactions":
        display_transaction_analysis()
    elif page == "🧾 Tax Reports":
        display_tax_reports()
    elif page == "⚙️ Settings":
        st.markdown("## ⚙️ Settings")
        st.info("🚧 Settings page coming soon!")
    
    # Footer
    st.markdown("---")
    st.markdown("""
    <div style='text-align: center; color: #666; font-size: 0.8rem;'>
        Portfolio Analytics Pro v2.0 | Built with ❤️ using Streamlit
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main() 