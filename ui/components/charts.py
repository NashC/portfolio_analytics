"""
Enhanced Chart Components for Portfolio Analytics Dashboard

This module provides optimized, reusable chart components with consistent styling,
performance optimizations, and interactive features.
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from typing import Dict, List, Optional, Tuple, Union
import logging

logger = logging.getLogger(__name__)

# Chart theme configuration
CHART_THEME = {
    'colors': {
        'primary': '#1f77b4',
        'secondary': '#ff7f0e',
        'success': '#2ca02c',
        'danger': '#d62728',
        'warning': '#ff7f0e',
        'info': '#17a2b8',
        'light': '#f8f9fa',
        'dark': '#343a40'
    },
    'layout': {
        'font_family': 'Arial, sans-serif',
        'font_size': 12,
        'title_font_size': 16,
        'grid_color': 'rgba(128, 128, 128, 0.2)',
        'background_color': 'white',
        'paper_bgcolor': 'white'
    }
}

def apply_chart_theme(fig: go.Figure, title: str = None, height: int = 400) -> go.Figure:
    """Apply consistent theme to all charts"""
    fig.update_layout(
        font_family=CHART_THEME['layout']['font_family'],
        font_size=CHART_THEME['layout']['font_size'],
        title_font_size=CHART_THEME['layout']['title_font_size'],
        plot_bgcolor=CHART_THEME['layout']['background_color'],
        paper_bgcolor=CHART_THEME['layout']['paper_bgcolor'],
        height=height,
        margin=dict(l=20, r=20, t=40, b=20),
        hovermode='x unified'
    )
    
    if title:
        fig.update_layout(title=dict(text=title, x=0.5, xanchor='center'))
    
    # Update axes
    fig.update_xaxes(
        showgrid=True,
        gridwidth=1,
        gridcolor=CHART_THEME['layout']['grid_color']
    )
    fig.update_yaxes(
        showgrid=True,
        gridwidth=1,
        gridcolor=CHART_THEME['layout']['grid_color']
    )
    
    return fig

@st.cache_data(ttl=300)
def create_portfolio_value_chart(
    portfolio_ts: pd.DataFrame,
    title: str = "Portfolio Value Over Time",
    height: int = 500
) -> go.Figure:
    """Create an optimized portfolio value chart with area fill"""
    
    if portfolio_ts.empty or 'total' not in portfolio_ts.columns:
        return create_empty_chart("No portfolio data available")
    
    fig = go.Figure()
    
    # Add portfolio value line with area fill
    fig.add_trace(go.Scatter(
        x=portfolio_ts.index,
        y=portfolio_ts['total'],
        mode='lines',
        name='Portfolio Value',
        line=dict(color=CHART_THEME['colors']['primary'], width=2),
        fill='tonexty',
        fillcolor=f"rgba(31, 119, 180, 0.1)",
        hovertemplate='<b>%{x}</b><br>Value: $%{y:,.2f}<extra></extra>'
    ))
    
    # Add trend line
    if len(portfolio_ts) > 1:
        x_numeric = np.arange(len(portfolio_ts))
        z = np.polyfit(x_numeric, portfolio_ts['total'], 1)
        trend_line = np.poly1d(z)(x_numeric)
        
        fig.add_trace(go.Scatter(
            x=portfolio_ts.index,
            y=trend_line,
            mode='lines',
            name='Trend',
            line=dict(color=CHART_THEME['colors']['secondary'], width=1, dash='dash'),
            hovertemplate='<b>%{x}</b><br>Trend: $%{y:,.2f}<extra></extra>'
        ))
    
    # Apply theme and formatting
    fig = apply_chart_theme(fig, title, height)
    fig.update_yaxes(title="Portfolio Value ($)")
    fig.update_xaxes(title="Date")
    
    return fig

@st.cache_data(ttl=300)
def create_returns_chart(
    returns: pd.Series,
    title: str = "Daily Returns",
    height: int = 400
) -> go.Figure:
    """Create a returns chart with color-coded bars"""
    
    if returns.empty:
        return create_empty_chart("No returns data available")
    
    # Convert to percentage
    returns_pct = returns * 100
    
    # Color bars based on positive/negative returns
    colors = [CHART_THEME['colors']['success'] if x >= 0 else CHART_THEME['colors']['danger'] 
              for x in returns_pct]
    
    fig = go.Figure()
    
    fig.add_trace(go.Bar(
        x=returns.index,
        y=returns_pct,
        name='Daily Returns',
        marker_color=colors,
        opacity=0.7,
        hovertemplate='<b>%{x}</b><br>Return: %{y:.2f}%<extra></extra>'
    ))
    
    # Add zero line
    fig.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.5)
    
    # Apply theme
    fig = apply_chart_theme(fig, title, height)
    fig.update_yaxes(title="Daily Return (%)")
    fig.update_xaxes(title="Date")
    
    return fig

@st.cache_data(ttl=300)
def create_drawdown_chart(
    drawdown: pd.Series,
    title: str = "Portfolio Drawdown",
    height: int = 400
) -> go.Figure:
    """Create a drawdown chart with filled area"""
    
    if drawdown.empty:
        return create_empty_chart("No drawdown data available")
    
    fig = go.Figure()
    
    fig.add_trace(go.Scatter(
        x=drawdown.index,
        y=drawdown,
        mode='lines',
        name='Drawdown',
        line=dict(color=CHART_THEME['colors']['danger'], width=2),
        fill='tonexty',
        fillcolor=f"rgba(214, 39, 40, 0.1)",
        hovertemplate='<b>%{x}</b><br>Drawdown: %{y:.2f}%<extra></extra>'
    ))
    
    # Add zero line
    fig.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.5)
    
    # Apply theme
    fig = apply_chart_theme(fig, title, height)
    fig.update_yaxes(title="Drawdown (%)")
    fig.update_xaxes(title="Date")
    
    return fig

@st.cache_data(ttl=300)
def create_asset_allocation_pie(
    allocation: pd.DataFrame,
    title: str = "Asset Allocation",
    height: int = 500
) -> go.Figure:
    """Create an interactive asset allocation pie chart"""
    
    if allocation.empty:
        return create_empty_chart("No allocation data available")
    
    # Use a professional color palette
    colors = px.colors.qualitative.Set3[:len(allocation)]
    
    fig = go.Figure(data=[go.Pie(
        labels=allocation['Asset'],
        values=allocation['Value'],
        hole=0.4,  # Donut chart
        marker=dict(colors=colors, line=dict(color='white', width=2)),
        textposition='inside',
        textinfo='percent+label',
        hovertemplate='<b>%{label}</b><br>Value: $%{value:,.2f}<br>Allocation: %{percent}<extra></extra>'
    )])
    
    # Apply theme
    fig = apply_chart_theme(fig, title, height)
    fig.update_layout(
        showlegend=True,
        legend=dict(
            orientation="v",
            yanchor="middle",
            y=0.5,
            xanchor="left",
            x=1.01
        )
    )
    
    return fig

@st.cache_data(ttl=300)
def create_asset_allocation_bar(
    allocation: pd.DataFrame,
    title: str = "Asset Allocation by Value",
    height: int = 400
) -> go.Figure:
    """Create a horizontal bar chart for asset allocation"""
    
    if allocation.empty:
        return create_empty_chart("No allocation data available")
    
    # Sort by value for better visualization
    allocation_sorted = allocation.sort_values('Value', ascending=True)
    
    fig = go.Figure()
    
    fig.add_trace(go.Bar(
        x=allocation_sorted['Value'],
        y=allocation_sorted['Asset'],
        orientation='h',
        name='Value',
        marker_color=CHART_THEME['colors']['primary'],
        hovertemplate='<b>%{y}</b><br>Value: $%{x:,.2f}<br>Allocation: %{customdata:.2f}%<extra></extra>',
        customdata=allocation_sorted['Allocation']
    ))
    
    # Apply theme
    fig = apply_chart_theme(fig, title, height)
    fig.update_xaxes(title="Value ($)")
    fig.update_yaxes(title="Asset")
    
    return fig

@st.cache_data(ttl=300)
def create_transaction_volume_chart(
    transactions: pd.DataFrame,
    title: str = "Transaction Volume Over Time",
    height: int = 400
) -> go.Figure:
    """Create a transaction volume chart"""
    
    if transactions.empty:
        return create_empty_chart("No transaction data available")
    
    # Calculate daily volume
    transactions['date'] = transactions['timestamp'].dt.date
    daily_volume = transactions.groupby('date').agg({
        'amount': lambda x: (transactions.loc[x.index, 'amount'] * 
                           transactions.loc[x.index, 'price']).sum()
    }).reset_index()
    daily_volume.columns = ['date', 'volume']
    
    fig = go.Figure()
    
    fig.add_trace(go.Bar(
        x=daily_volume['date'],
        y=daily_volume['volume'],
        name='Daily Volume',
        marker_color=CHART_THEME['colors']['info'],
        hovertemplate='<b>%{x}</b><br>Volume: $%{y:,.2f}<extra></extra>'
    ))
    
    # Apply theme
    fig = apply_chart_theme(fig, title, height)
    fig.update_yaxes(title="Volume ($)")
    fig.update_xaxes(title="Date")
    
    return fig

@st.cache_data(ttl=300)
def create_correlation_heatmap(
    returns_data: pd.DataFrame,
    title: str = "Asset Correlation Matrix",
    height: int = 500
) -> go.Figure:
    """Create a correlation heatmap for assets"""
    
    if returns_data.empty:
        return create_empty_chart("No correlation data available")
    
    # Calculate correlation matrix
    correlation_matrix = returns_data.corr()
    
    fig = go.Figure(data=go.Heatmap(
        z=correlation_matrix.values,
        x=correlation_matrix.columns,
        y=correlation_matrix.columns,
        colorscale='RdBu',
        zmid=0,
        text=correlation_matrix.round(2).values,
        texttemplate="%{text}",
        textfont={"size": 10},
        hovertemplate='<b>%{x} vs %{y}</b><br>Correlation: %{z:.3f}<extra></extra>'
    ))
    
    # Apply theme
    fig = apply_chart_theme(fig, title, height)
    fig.update_layout(
        xaxis_title="Asset",
        yaxis_title="Asset"
    )
    
    return fig

@st.cache_data(ttl=300)
def create_performance_comparison_chart(
    metrics_data: Dict[str, float],
    benchmark_data: Optional[Dict[str, float]] = None,
    title: str = "Performance Metrics",
    height: int = 400
) -> go.Figure:
    """Create a performance comparison chart"""
    
    if not metrics_data:
        return create_empty_chart("No performance data available")
    
    metrics = list(metrics_data.keys())
    values = list(metrics_data.values())
    
    fig = go.Figure()
    
    # Portfolio metrics
    fig.add_trace(go.Bar(
        x=metrics,
        y=values,
        name='Portfolio',
        marker_color=CHART_THEME['colors']['primary'],
        hovertemplate='<b>%{x}</b><br>Value: %{y:.2f}<extra></extra>'
    ))
    
    # Benchmark comparison if provided
    if benchmark_data:
        benchmark_values = [benchmark_data.get(metric, 0) for metric in metrics]
        fig.add_trace(go.Bar(
            x=metrics,
            y=benchmark_values,
            name='Benchmark',
            marker_color=CHART_THEME['colors']['secondary'],
            hovertemplate='<b>%{x}</b><br>Benchmark: %{y:.2f}<extra></extra>'
        ))
    
    # Apply theme
    fig = apply_chart_theme(fig, title, height)
    fig.update_yaxes(title="Value")
    fig.update_xaxes(title="Metric")
    
    return fig

def create_empty_chart(message: str = "No data available") -> go.Figure:
    """Create an empty chart with a message"""
    fig = go.Figure()
    
    fig.add_annotation(
        text=message,
        xref="paper", yref="paper",
        x=0.5, y=0.5,
        xanchor='center', yanchor='middle',
        showarrow=False,
        font=dict(size=16, color="gray")
    )
    
    fig = apply_chart_theme(fig, height=300)
    fig.update_xaxes(showticklabels=False)
    fig.update_yaxes(showticklabels=False)
    
    return fig

@st.cache_data(ttl=300)
def create_multi_asset_performance_chart(
    portfolio_ts: pd.DataFrame,
    title: str = "Multi-Asset Performance",
    height: int = 600
) -> go.Figure:
    """Create a multi-asset performance comparison chart"""
    
    if portfolio_ts.empty:
        return create_empty_chart("No portfolio data available")
    
    # Normalize to percentage change from first value
    normalized_data = portfolio_ts.div(portfolio_ts.iloc[0]) * 100 - 100
    
    fig = go.Figure()
    
    # Add traces for each asset (excluding 'total')
    colors = px.colors.qualitative.Set1
    color_idx = 0
    
    for column in normalized_data.columns:
        if column != 'total':
            fig.add_trace(go.Scatter(
                x=normalized_data.index,
                y=normalized_data[column],
                mode='lines',
                name=column,
                line=dict(color=colors[color_idx % len(colors)], width=2),
                hovertemplate=f'<b>{column}</b><br>%{{x}}<br>Return: %{{y:.2f}}%<extra></extra>'
            ))
            color_idx += 1
    
    # Add total portfolio performance with emphasis
    if 'total' in normalized_data.columns:
        fig.add_trace(go.Scatter(
            x=normalized_data.index,
            y=normalized_data['total'],
            mode='lines',
            name='Total Portfolio',
            line=dict(color='black', width=3),
            hovertemplate='<b>Total Portfolio</b><br>%{x}<br>Return: %{y:.2f}%<extra></extra>'
        ))
    
    # Add zero line
    fig.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.5)
    
    # Apply theme
    fig = apply_chart_theme(fig, title, height)
    fig.update_yaxes(title="Cumulative Return (%)")
    fig.update_xaxes(title="Date")
    fig.update_layout(legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01))
    
    return fig

def display_chart_with_controls(
    chart_func,
    data,
    chart_title: str,
    **kwargs
) -> None:
    """Display a chart with interactive controls"""
    
    col1, col2 = st.columns([3, 1])
    
    with col2:
        st.markdown("#### Chart Controls")
        
        # Height control
        height = st.slider("Chart Height", 300, 800, 500, 50, key=f"{chart_title}_height")
        
        # Download button
        if st.button("📥 Download Chart", key=f"{chart_title}_download"):
            st.info("Chart download functionality coming soon!")
    
    with col1:
        # Create and display chart
        fig = chart_func(data, title=chart_title, height=height, **kwargs)
        st.plotly_chart(fig, use_container_width=True)

# Chart factory for easy chart creation
class ChartFactory:
    """Factory class for creating charts with consistent styling"""
    
    @staticmethod
    def portfolio_overview(portfolio_ts: pd.DataFrame, returns: pd.Series, drawdown: pd.Series) -> go.Figure:
        """Create a comprehensive portfolio overview chart"""
        
        fig = make_subplots(
            rows=3, cols=1,
            subplot_titles=('Portfolio Value', 'Daily Returns (%)', 'Drawdown (%)'),
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
                line=dict(color=CHART_THEME['colors']['primary'], width=2),
                fill='tonexty',
                fillcolor='rgba(31, 119, 180, 0.1)'
            ),
            row=1, col=1
        )
        
        # Daily returns
        colors = [CHART_THEME['colors']['success'] if x >= 0 else CHART_THEME['colors']['danger'] 
                  for x in returns]
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
                line=dict(color=CHART_THEME['colors']['danger'], width=1),
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
        
        # Apply theme to axes
        fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor=CHART_THEME['layout']['grid_color'])
        fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor=CHART_THEME['layout']['grid_color'])
        
        return fig 