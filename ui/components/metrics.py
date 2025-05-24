"""
Enhanced Metrics Components for Portfolio Analytics Dashboard

This module provides reusable metric display components with consistent styling,
animations, and interactive features.
"""

import streamlit as st
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Union, Any, Tuple
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

def display_metric_card(
    title: str,
    value: Union[str, float, int],
    delta: Optional[Union[str, float, int]] = None,
    delta_color: str = "normal",
    help_text: Optional[str] = None,
    format_type: str = "auto"
) -> None:
    """
    Display an enhanced metric card with custom styling
    
    Args:
        title: The metric title
        value: The main metric value
        delta: The change/delta value
        delta_color: Color for delta ("normal", "inverse", "off")
        help_text: Optional help text
        format_type: How to format the value ("currency", "percentage", "number", "auto")
    """
    
    # Format the value based on type
    if format_type == "currency" and isinstance(value, (int, float)):
        formatted_value = f"${value:,.2f}"
    elif format_type == "percentage" and isinstance(value, (int, float)):
        formatted_value = f"{value:.2f}%"
    elif format_type == "number" and isinstance(value, (int, float)):
        formatted_value = f"{value:,.0f}"
    else:
        formatted_value = str(value)
    
    # Format delta if provided
    formatted_delta = None
    if delta is not None:
        if isinstance(delta, (int, float)):
            if format_type == "currency":
                formatted_delta = f"${delta:,.2f}"
            elif format_type == "percentage":
                formatted_delta = f"{delta:+.2f}%"
            else:
                formatted_delta = f"{delta:+,.2f}"
        else:
            formatted_delta = str(delta)
    
    # Use Streamlit's built-in metric with enhanced styling
    st.metric(
        label=title,
        value=formatted_value,
        delta=formatted_delta,
        delta_color=delta_color,
        help=help_text
    )

def display_kpi_grid(metrics: Dict[str, Dict[str, Any]], columns: int = 4) -> None:
    """
    Display a grid of KPI metrics
    
    Args:
        metrics: Dictionary of metric configurations
        columns: Number of columns in the grid
    """
    
    metric_items = list(metrics.items())
    
    # Create columns
    cols = st.columns(columns)
    
    for i, (key, config) in enumerate(metric_items):
        col_idx = i % columns
        
        with cols[col_idx]:
            display_metric_card(
                title=config.get('title', key),
                value=config.get('value', 0),
                delta=config.get('delta'),
                delta_color=config.get('delta_color', 'normal'),
                help_text=config.get('help'),
                format_type=config.get('format', 'auto')
            )

def display_performance_summary(metrics: Dict[str, float]) -> None:
    """Display a comprehensive performance summary"""
    
    st.markdown("### 📈 Performance Summary")
    
    # Define the metrics configuration
    performance_metrics = {
        'total_return': {
            'title': 'Total Return',
            'value': metrics.get('total_return', 0),
            'format': 'percentage',
            'help': 'Total portfolio return since inception'
        },
        'annualized_return': {
            'title': 'Annualized Return',
            'value': metrics.get('annualized_return', 0),
            'format': 'percentage',
            'help': 'Annualized portfolio return'
        },
        'volatility': {
            'title': 'Volatility',
            'value': metrics.get('volatility', 0),
            'format': 'percentage',
            'help': 'Annualized portfolio volatility'
        },
        'sharpe_ratio': {
            'title': 'Sharpe Ratio',
            'value': metrics.get('sharpe_ratio', 0),
            'format': 'number',
            'help': 'Risk-adjusted return measure'
        }
    }
    
    display_kpi_grid(performance_metrics, columns=4)

def display_portfolio_summary(
    current_value: float,
    cost_basis: float,
    unrealized_pnl: float,
    realized_pnl: Optional[float] = None
) -> None:
    """Display portfolio value summary"""
    
    st.markdown("### 💰 Portfolio Summary")
    
    # Calculate percentage gain/loss
    pnl_percentage = (unrealized_pnl / cost_basis * 100) if cost_basis > 0 else 0
    
    portfolio_metrics = {
        'current_value': {
            'title': 'Current Value',
            'value': current_value,
            'format': 'currency',
            'help': 'Current market value of portfolio'
        },
        'cost_basis': {
            'title': 'Cost Basis',
            'value': cost_basis,
            'format': 'currency',
            'help': 'Total amount invested'
        },
        'unrealized_pnl': {
            'title': 'Unrealized P&L',
            'value': unrealized_pnl,
            'delta': f"{pnl_percentage:.2f}%",
            'delta_color': 'normal' if unrealized_pnl >= 0 else 'inverse',
            'format': 'currency',
            'help': 'Unrealized profit/loss'
        }
    }
    
    if realized_pnl is not None:
        portfolio_metrics['realized_pnl'] = {
            'title': 'Realized P&L',
            'value': realized_pnl,
            'format': 'currency',
            'help': 'Realized profit/loss from sales'
        }
    
    display_kpi_grid(portfolio_metrics, columns=4)

def display_risk_metrics(metrics: Dict[str, float]) -> None:
    """Display risk-related metrics"""
    
    st.markdown("### ⚠️ Risk Metrics")
    
    risk_metrics = {
        'max_drawdown': {
            'title': 'Max Drawdown',
            'value': metrics.get('max_drawdown', 0),
            'format': 'percentage',
            'delta_color': 'inverse',
            'help': 'Maximum peak-to-trough decline'
        },
        'var_95': {
            'title': 'VaR (95%)',
            'value': metrics.get('var_95', 0),
            'format': 'percentage',
            'help': 'Value at Risk at 95% confidence level'
        },
        'best_day': {
            'title': 'Best Day',
            'value': metrics.get('best_day', 0),
            'format': 'percentage',
            'delta_color': 'normal',
            'help': 'Best single day return'
        },
        'worst_day': {
            'title': 'Worst Day',
            'value': metrics.get('worst_day', 0),
            'format': 'percentage',
            'delta_color': 'inverse',
            'help': 'Worst single day return'
        }
    }
    
    display_kpi_grid(risk_metrics, columns=4)

def display_transaction_metrics(transactions: pd.DataFrame) -> None:
    """Display transaction-related metrics"""
    
    if transactions.empty:
        st.info("No transaction data available")
        return
    
    st.markdown("### 📊 Transaction Metrics")
    
    # Calculate metrics
    total_transactions = len(transactions)
    total_volume = (transactions['amount'] * transactions['price']).sum()
    avg_transaction_size = total_volume / total_transactions if total_transactions > 0 else 0
    total_fees = transactions['fees'].sum()
    
    # Date range
    date_range = (transactions['timestamp'].max() - transactions['timestamp'].min()).days
    
    transaction_metrics = {
        'total_transactions': {
            'title': 'Total Transactions',
            'value': total_transactions,
            'format': 'number',
            'help': 'Total number of transactions'
        },
        'total_volume': {
            'title': 'Total Volume',
            'value': total_volume,
            'format': 'currency',
            'help': 'Total transaction volume'
        },
        'avg_size': {
            'title': 'Avg Transaction Size',
            'value': avg_transaction_size,
            'format': 'currency',
            'help': 'Average transaction size'
        },
        'total_fees': {
            'title': 'Total Fees',
            'value': total_fees,
            'format': 'currency',
            'help': 'Total fees paid'
        }
    }
    
    display_kpi_grid(transaction_metrics, columns=4)

def display_asset_metrics(allocation: pd.DataFrame) -> None:
    """Display asset allocation metrics"""
    
    if allocation.empty:
        st.info("No allocation data available")
        return
    
    st.markdown("### 🏗️ Asset Metrics")
    
    # Calculate metrics
    total_assets = len(allocation)
    largest_holding = allocation['Allocation'].max() if not allocation.empty else 0
    smallest_holding = allocation['Allocation'].min() if not allocation.empty else 0
    concentration_ratio = allocation.nlargest(3, 'Allocation')['Allocation'].sum() if len(allocation) >= 3 else 100
    
    asset_metrics = {
        'total_assets': {
            'title': 'Total Assets',
            'value': total_assets,
            'format': 'number',
            'help': 'Number of different assets held'
        },
        'largest_holding': {
            'title': 'Largest Holding',
            'value': largest_holding,
            'format': 'percentage',
            'help': 'Percentage of largest single holding'
        },
        'concentration': {
            'title': 'Top 3 Concentration',
            'value': concentration_ratio,
            'format': 'percentage',
            'help': 'Percentage held in top 3 assets'
        },
        'diversification': {
            'title': 'Diversification Score',
            'value': min(100, (total_assets * 10) - (largest_holding * 2)),
            'format': 'number',
            'help': 'Simple diversification score (0-100)'
        }
    }
    
    display_kpi_grid(asset_metrics, columns=4)

def display_time_period_selector() -> Tuple[datetime, datetime]:
    """Display a time period selector and return selected dates"""
    
    st.markdown("### 📅 Time Period")
    
    col1, col2, col3 = st.columns([1, 1, 2])
    
    with col1:
        # Quick period buttons
        period = st.selectbox(
            "Quick Select",
            ["Custom", "1M", "3M", "6M", "1Y", "2Y", "All Time"],
            index=6  # Default to "All Time"
        )
    
    # Calculate date range based on selection
    end_date = datetime.now().date()
    
    if period == "1M":
        start_date = end_date - timedelta(days=30)
    elif period == "3M":
        start_date = end_date - timedelta(days=90)
    elif period == "6M":
        start_date = end_date - timedelta(days=180)
    elif period == "1Y":
        start_date = end_date - timedelta(days=365)
    elif period == "2Y":
        start_date = end_date - timedelta(days=730)
    elif period == "All Time":
        start_date = datetime(2020, 1, 1).date()  # Default start
    else:  # Custom
        with col2:
            start_date = st.date_input("Start Date", value=datetime(2023, 1, 1).date())
        with col3:
            end_date = st.date_input("End Date", value=end_date)
    
    if period != "Custom":
        with col2:
            st.date_input("Start Date", value=start_date, disabled=True)
        with col3:
            st.date_input("End Date", value=end_date, disabled=True)
    
    return datetime.combine(start_date, datetime.min.time()), datetime.combine(end_date, datetime.max.time())

def display_status_indicator(
    status: str,
    message: str,
    details: Optional[str] = None
) -> None:
    """Display a status indicator with message"""
    
    status_config = {
        'success': {'icon': '✅', 'color': 'green'},
        'warning': {'icon': '⚠️', 'color': 'orange'},
        'error': {'icon': '❌', 'color': 'red'},
        'info': {'icon': 'ℹ️', 'color': 'blue'},
        'loading': {'icon': '🔄', 'color': 'gray'}
    }
    
    config = status_config.get(status, status_config['info'])
    
    st.markdown(f"""
    <div style="
        padding: 10px;
        border-left: 4px solid {config['color']};
        background-color: rgba(128, 128, 128, 0.1);
        margin: 10px 0;
    ">
        <strong>{config['icon']} {message}</strong>
        {f'<br><small>{details}</small>' if details else ''}
    </div>
    """, unsafe_allow_html=True)

def display_progress_bar(
    current: float,
    target: float,
    title: str,
    format_type: str = "currency"
) -> None:
    """Display a progress bar towards a target"""
    
    progress = min(current / target, 1.0) if target > 0 else 0
    percentage = progress * 100
    
    # Format values
    if format_type == "currency":
        current_str = f"${current:,.2f}"
        target_str = f"${target:,.2f}"
    elif format_type == "percentage":
        current_str = f"{current:.2f}%"
        target_str = f"{target:.2f}%"
    else:
        current_str = f"{current:,.0f}"
        target_str = f"{target:,.0f}"
    
    st.markdown(f"**{title}**")
    st.progress(progress)
    st.markdown(f"{current_str} / {target_str} ({percentage:.1f}%)")

def display_comparison_table(
    data: Dict[str, Dict[str, Any]],
    title: str = "Comparison"
) -> None:
    """Display a comparison table with metrics"""
    
    st.markdown(f"### {title}")
    
    # Convert to DataFrame for better display
    df = pd.DataFrame(data).T
    
    # Format numeric columns
    for col in df.columns:
        if df[col].dtype in ['float64', 'int64']:
            df[col] = df[col].apply(lambda x: f"{x:,.2f}" if pd.notna(x) else "N/A")
    
    st.dataframe(df, use_container_width=True)

def display_alert_banner(
    message: str,
    alert_type: str = "info",
    dismissible: bool = True
) -> None:
    """Display an alert banner at the top of the page"""
    
    alert_styles = {
        'info': {'bg': '#d1ecf1', 'border': '#bee5eb', 'text': '#0c5460'},
        'success': {'bg': '#d4edda', 'border': '#c3e6cb', 'text': '#155724'},
        'warning': {'bg': '#fff3cd', 'border': '#ffeaa7', 'text': '#856404'},
        'error': {'bg': '#f8d7da', 'border': '#f5c6cb', 'text': '#721c24'}
    }
    
    style = alert_styles.get(alert_type, alert_styles['info'])
    
    dismiss_script = """
    <script>
    function dismissAlert(id) {
        document.getElementById(id).style.display = 'none';
    }
    </script>
    """ if dismissible else ""
    
    dismiss_button = """
    <button onclick="dismissAlert('alert-banner')" style="
        float: right;
        background: none;
        border: none;
        font-size: 18px;
        cursor: pointer;
        color: inherit;
    ">&times;</button>
    """ if dismissible else ""
    
    st.markdown(f"""
    {dismiss_script}
    <div id="alert-banner" style="
        background-color: {style['bg']};
        border: 1px solid {style['border']};
        color: {style['text']};
        padding: 15px;
        margin: 10px 0;
        border-radius: 4px;
    ">
        {dismiss_button}
        {message}
    </div>
    """, unsafe_allow_html=True)

class MetricsCalculator:
    """Helper class for calculating various portfolio metrics"""
    
    @staticmethod
    def calculate_sharpe_ratio(returns: pd.Series, risk_free_rate: float = 0.02) -> float:
        """Calculate Sharpe ratio"""
        if returns.empty or returns.std() == 0:
            return 0.0
        
        excess_returns = returns.mean() * 252 - risk_free_rate
        volatility = returns.std() * np.sqrt(252)
        
        return excess_returns / volatility
    
    @staticmethod
    def calculate_max_drawdown(prices: pd.Series) -> float:
        """Calculate maximum drawdown"""
        if prices.empty:
            return 0.0
        
        rolling_max = prices.expanding().max()
        drawdown = (prices / rolling_max - 1) * 100
        
        return drawdown.min()
    
    @staticmethod
    def calculate_var(returns: pd.Series, confidence: float = 0.05) -> float:
        """Calculate Value at Risk"""
        if returns.empty:
            return 0.0
        
        return np.percentile(returns, confidence * 100) * 100
    
    @staticmethod
    def calculate_volatility(returns: pd.Series, annualize: bool = True) -> float:
        """Calculate volatility"""
        if returns.empty:
            return 0.0
        
        vol = returns.std()
        
        if annualize:
            vol *= np.sqrt(252)
        
        return vol * 100 