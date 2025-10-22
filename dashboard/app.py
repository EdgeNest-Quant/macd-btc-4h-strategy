"""
🤖 Drift MACD Trading Bot Dashboard
Professional multi-page analytics dashboard for BTC-PERP 4H MACD strategy
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
import numpy as np
from pathlib import Path
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from dashboard.utils import (
    load_trades_data,
    load_latest_log,
    calculate_performance_metrics,
    calculate_risk_metrics,
    get_trade_statistics,
    parse_log_events,
    get_historical_data_mock,
    get_trade_signals_for_chart
)

# Page configuration
st.set_page_config(
    page_title="Drift MACD Bot Dashboard",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
    <style>
    .main {
        padding: 0rem 1rem;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 20px;
        border-radius: 10px;
        margin: 10px 0;
    }
    .positive {
        color: #00ff00;
    }
    .negative {
        color: #ff4444;
    }
    h1 {
        color: #1f77b4;
    }
    /* Remove white background from metric cards for better visibility */
    .stMetric {
        background-color: transparent;
        padding: 15px;
        border-radius: 8px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    /* Improve metric label visibility */
    .stMetric label {
        color: inherit;
        font-weight: 600;
    }
    /* Improve metric value visibility */
    .stMetric [data-testid="stMetricValue"] {
        color: inherit;
        font-size: 1.8rem;
        font-weight: 600;
    }
    /* Improve delta visibility */
    .stMetric [data-testid="stMetricDelta"] {
        font-weight: 500;
    }
    </style>
""", unsafe_allow_html=True)

# Sidebar Navigation
st.sidebar.title("🤖 Drift MACD Bot")
st.sidebar.markdown("---")

page = st.sidebar.radio(
    "Navigation",
    [
        "📊 Overview",
        "💰 Performance Analytics", 
        "📈 Trade Analysis",
        "📊 Live Chart",
        "⚠️ Risk Metrics",
        "🔴 Live Monitoring",
        "📜 Trade History"
    ]
)

st.sidebar.markdown("---")
st.sidebar.markdown("### Strategy Info")
st.sidebar.info("""
**Symbol:** BTC-PERP  
**Timeframe:** 4 Hours  
**Strategy:** MACD Momentum  
**Environment:** Devnet
""")

# Load data
try:
    trades_df = load_trades_data()
    log_data = load_latest_log()
    metrics = calculate_performance_metrics(trades_df)
    risk_metrics = calculate_risk_metrics(trades_df)
    trade_stats = get_trade_statistics(trades_df)
except Exception as e:
    st.error(f"❌ Error loading data: {str(e)}")
    st.stop()

# ============================================================================
# 📊 OVERVIEW PAGE
# ============================================================================
if page == "📊 Overview":
    st.title("📊 Trading Bot Overview")
    st.markdown("---")
    
    # Key Metrics Row
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        total_pnl = metrics.get('total_realized_pnl', 0)
        pnl_color = "normal" if total_pnl >= 0 else "inverse"
        st.metric(
            "Total P&L", 
            f"${total_pnl:.2f}",
            delta=f"{metrics.get('total_pnl_pct', 0):.2f}%",
            delta_color=pnl_color
        )
    
    with col2:
        st.metric(
            "Win Rate",
            f"{metrics.get('win_rate', 0):.1f}%",
            delta=f"{trade_stats.get('winning_trades', 0)}/{trade_stats.get('total_trades', 0)} trades"
        )
    
    with col3:
        st.metric(
            "Total Trades",
            trade_stats.get('total_trades', 0),
            delta=f"{trade_stats.get('closed_trades', 0)} closed"
        )
    
    with col4:
        st.metric(
            "Sharpe Ratio",
            f"{risk_metrics.get('sharpe_ratio', 0):.2f}",
            delta="Risk-adjusted return"
        )
    
    with col5:
        st.metric(
            "Max Drawdown",
            f"{risk_metrics.get('max_drawdown_pct', 0):.2f}%",
            delta="Portfolio risk",
            delta_color="inverse"
        )
    
    st.markdown("---")
    
    # Charts Row
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("💵 Cumulative P&L")
        if not trades_df.empty and 'pnl' in trades_df.columns:
            closed_trades = trades_df[trades_df['status'] == 'CLOSED'].copy()
            if not closed_trades.empty:
                closed_trades = closed_trades.sort_values('timestamp')
                closed_trades['cumulative_pnl'] = closed_trades['pnl'].cumsum()
                
                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=closed_trades['timestamp'],
                    y=closed_trades['cumulative_pnl'],
                    mode='lines+markers',
                    name='Cumulative P&L',
                    line=dict(color='#1f77b4', width=2),
                    fill='tozeroy',
                    fillcolor='rgba(31, 119, 180, 0.1)'
                ))
                fig.update_layout(
                    height=400,
                    hovermode='x unified',
                    xaxis_title="Date",
                    yaxis_title="Cumulative P&L ($)",
                    showlegend=False
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No closed trades yet")
        else:
            st.info("No trade data available")
    
    with col2:
        st.subheader("🎯 Win/Loss Distribution")
        if trade_stats.get('total_trades', 0) > 0:
            fig = go.Figure(data=[go.Pie(
                labels=['Winning Trades', 'Losing Trades', 'Open Positions'],
                values=[
                    trade_stats.get('winning_trades', 0),
                    trade_stats.get('losing_trades', 0),
                    trade_stats.get('open_positions', 0)
                ],
                hole=0.4,
                marker=dict(colors=['#00ff88', '#ff4444', '#ffaa00']),
                textinfo='label+value+percent'
            )])
            fig.update_layout(height=400)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No trades executed yet")
    
    # Recent Activity
    st.markdown("---")
    st.subheader("📜 Recent Trades")
    if not trades_df.empty:
        recent = trades_df.head(10)[['timestamp', 'symbol', 'side', 'price', 'quantity', 'pnl', 'status']].copy()
        recent['price'] = recent['price'].apply(lambda x: f"${x:,.2f}")
        recent['quantity'] = recent['quantity'].apply(lambda x: f"{x:.4f}")
        recent['pnl'] = recent['pnl'].apply(lambda x: f"${x:.2f}" if pd.notna(x) else "—")
        st.dataframe(recent, use_container_width=True, height=400)
    else:
        st.info("No trades executed yet")

# ============================================================================
# 💰 PERFORMANCE ANALYTICS PAGE
# ============================================================================
elif page == "💰 Performance Analytics":
    st.title("💰 Performance Analytics")
    st.markdown("---")
    
    # Performance Metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Realized P&L", f"${metrics.get('total_realized_pnl', 0):.2f}")
        st.metric("Total Unrealized P&L", f"${metrics.get('total_unrealized_pnl', 0):.2f}")
    
    with col2:
        st.metric("Average Win", f"${metrics.get('avg_win', 0):.2f}")
        st.metric("Average Loss", f"${metrics.get('avg_loss', 0):.2f}")
    
    with col3:
        st.metric("Profit Factor", f"{metrics.get('profit_factor', 0):.2f}")
        st.metric("Win Rate", f"{metrics.get('win_rate', 0):.1f}%")
    
    with col4:
        st.metric("Best Trade", f"${metrics.get('best_trade', 0):.2f}")
        st.metric("Worst Trade", f"${metrics.get('worst_trade', 0):.2f}")
    
    st.markdown("---")
    
    # Equity Curve
    st.subheader("📈 Equity Curve")
    if not trades_df.empty:
        closed_trades = trades_df[trades_df['status'] == 'CLOSED'].copy()
        if not closed_trades.empty:
            closed_trades = closed_trades.sort_values('timestamp')
            closed_trades['cumulative_pnl'] = closed_trades['pnl'].cumsum()
            
            # Calculate drawdown
            closed_trades['running_max'] = closed_trades['cumulative_pnl'].cummax()
            closed_trades['drawdown'] = closed_trades['cumulative_pnl'] - closed_trades['running_max']
            
            fig = make_subplots(
                rows=2, cols=1,
                shared_xaxes=True,
                vertical_spacing=0.05,
                subplot_titles=('Equity Curve', 'Drawdown'),
                row_heights=[0.7, 0.3]
            )
            
            # Equity curve
            fig.add_trace(
                go.Scatter(
                    x=closed_trades['timestamp'],
                    y=closed_trades['cumulative_pnl'],
                    name='Cumulative P&L',
                    line=dict(color='#1f77b4', width=2),
                    fill='tozeroy'
                ),
                row=1, col=1
            )
            
            # Drawdown
            fig.add_trace(
                go.Scatter(
                    x=closed_trades['timestamp'],
                    y=closed_trades['drawdown'],
                    name='Drawdown',
                    line=dict(color='#ff4444', width=2),
                    fill='tozeroy',
                    fillcolor='rgba(255, 68, 68, 0.2)'
                ),
                row=2, col=1
            )
            
            fig.update_layout(height=600, hovermode='x unified', showlegend=True)
            fig.update_xaxes(title_text="Date", row=2, col=1)
            fig.update_yaxes(title_text="P&L ($)", row=1, col=1)
            fig.update_yaxes(title_text="Drawdown ($)", row=2, col=1)
            
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No closed trades yet")
    
    # P&L Distribution
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📊 P&L Distribution")
        if not trades_df.empty:
            closed_trades = trades_df[trades_df['status'] == 'CLOSED']
            if not closed_trades.empty and 'pnl' in closed_trades.columns:
                fig = go.Figure(data=[go.Histogram(
                    x=closed_trades['pnl'],
                    nbinsx=20,
                    marker=dict(
                        color=closed_trades['pnl'],
                        colorscale=['red', 'yellow', 'green'],
                        showscale=True
                    )
                )])
                fig.update_layout(
                    height=400,
                    xaxis_title="P&L ($)",
                    yaxis_title="Frequency",
                    showlegend=False
                )
                st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.subheader("⏱️ Trade Duration Analysis")
        if not trades_df.empty:
            closed_trades = trades_df[trades_df['status'] == 'CLOSED'].copy()
            if not closed_trades.empty and 'duration_seconds' in closed_trades.columns:
                closed_trades['duration_hours'] = closed_trades['duration_seconds'] / 3600
                
                fig = go.Figure(data=[go.Box(
                    y=closed_trades['duration_hours'],
                    name='Duration',
                    marker=dict(color='#1f77b4')
                )])
                fig.update_layout(
                    height=400,
                    yaxis_title="Duration (hours)",
                    showlegend=False
                )
                st.plotly_chart(fig, use_container_width=True)

# ============================================================================
# 📈 TRADE ANALYSIS PAGE
# ============================================================================
elif page == "📈 Trade Analysis":
    st.title("📈 Trade Analysis")
    st.markdown("---")
    
    # Trade Statistics
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Total Trades", trade_stats.get('total_trades', 0))
        st.metric("Closed Trades", trade_stats.get('closed_trades', 0))
        st.metric("Open Positions", trade_stats.get('open_positions', 0))
    
    with col2:
        st.metric("Long Trades", trade_stats.get('long_trades', 0))
        st.metric("Short Trades", trade_stats.get('short_trades', 0))
        st.metric("Avg Position Size", f"{trade_stats.get('avg_position_size', 0):.4f} BTC")
    
    with col3:
        st.metric("Winning Trades", trade_stats.get('winning_trades', 0))
        st.metric("Losing Trades", trade_stats.get('losing_trades', 0))
        st.metric("Avg Hold Time", f"{trade_stats.get('avg_hold_time_hours', 0):.1f}h")
    
    st.markdown("---")
    
    # Trade Timeline
    st.subheader("📅 Trade Timeline")
    if not trades_df.empty:
        fig = go.Figure()
        
        # Separate buys and sells
        buys = trades_df[trades_df['side'] == 'BUY']
        sells = trades_df[trades_df['side'] == 'SELL']
        closes = trades_df[trades_df['side'] == 'CLOSE']
        
        if not buys.empty:
            fig.add_trace(go.Scatter(
                x=buys['timestamp'],
                y=buys['price'],
                mode='markers',
                name='BUY',
                marker=dict(color='green', size=12, symbol='triangle-up')
            ))
        
        if not sells.empty:
            fig.add_trace(go.Scatter(
                x=sells['timestamp'],
                y=sells['price'],
                mode='markers',
                name='SELL',
                marker=dict(color='red', size=12, symbol='triangle-down')
            ))
        
        if not closes.empty:
            fig.add_trace(go.Scatter(
                x=closes['timestamp'],
                y=closes['price'],
                mode='markers',
                name='CLOSE',
                marker=dict(color='blue', size=10, symbol='x')
            ))
        
        fig.update_layout(
            height=500,
            hovermode='x unified',
            xaxis_title="Date",
            yaxis_title="Price ($)"
        )
        st.plotly_chart(fig, use_container_width=True)
    
    # Side by side comparison
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📊 Long vs Short Performance")
        if not trades_df.empty:
            closed = trades_df[trades_df['status'] == 'CLOSED'].copy()
            if not closed.empty:
                # Determine if trade was long or short based on entry side
                long_pnl = closed[closed['side'] == 'BUY']['pnl'].sum() if 'BUY' in closed['side'].values else 0
                short_pnl = closed[closed['side'] == 'SELL']['pnl'].sum() if 'SELL' in closed['side'].values else 0
                
                fig = go.Figure(data=[go.Bar(
                    x=['Long Trades', 'Short Trades'],
                    y=[long_pnl, short_pnl],
                    marker=dict(color=['green', 'red'])
                )])
                fig.update_layout(height=400, yaxis_title="Total P&L ($)")
                st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.subheader("⏰ Hourly Trade Distribution")
        if not trades_df.empty:
            trades_df['hour'] = pd.to_datetime(trades_df['timestamp']).dt.hour
            hourly = trades_df.groupby('hour').size().reset_index(name='count')
            
            fig = go.Figure(data=[go.Bar(
                x=hourly['hour'],
                y=hourly['count'],
                marker=dict(color='#1f77b4')
            )])
            fig.update_layout(
                height=400,
                xaxis_title="Hour of Day (UTC)",
                yaxis_title="Number of Trades"
            )
            st.plotly_chart(fig, use_container_width=True)

# ============================================================================
# 📊 LIVE CHART PAGE
# ============================================================================
elif page == "📊 Live Chart":
    st.title("📊 Live Chart - BTC-PERP 4H with MACD Strategy")
    st.markdown("---")
    
    # Info banner
    st.info("""
    **Your Bot's View**: This chart shows BTC-PERP on 4-hour timeframe with your exact strategy indicators:
    - **MACD (6, 10, 2)**: Fast momentum indicator
    - **EMA (168)**: Long-term trend filter (1 week on 4H)
    - **Trade Signals**: Your actual entry/exit points overlaid
    """)
    
    # Fetch historical data
    with st.spinner("Loading chart data..."):
        chart_data = get_historical_data_mock('BTC-PERP', '4h', periods=200)
        signals = get_trade_signals_for_chart(trades_df)
    
    # Main Chart: Candlestick + EMA
    st.subheader("💹 BTC-PERP Price Chart with EMA Filter")
    
    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        subplot_titles=('BTC-PERP 4H Chart', 'MACD Indicator (6, 10, 2)'),
        row_heights=[0.7, 0.3]
    )
    
    # Candlestick chart
    fig.add_trace(
        go.Candlestick(
            x=chart_data['timestamp'],
            open=chart_data['open'],
            high=chart_data['high'],
            low=chart_data['low'],
            close=chart_data['close'],
            name='BTC-PERP',
            increasing_line_color='#00ff88',
            decreasing_line_color='#ff4444'
        ),
        row=1, col=1
    )
    
    # EMA 168 overlay
    if 'EMA_168' in chart_data.columns:
        fig.add_trace(
            go.Scatter(
                x=chart_data['timestamp'],
                y=chart_data['EMA_168'],
                name='EMA 168 (Trend Filter)',
                line=dict(color='#ff9800', width=2),
                opacity=0.8
            ),
            row=1, col=1
        )
    
    # Add BUY signals
    if not signals['buy_signals'].empty:
        fig.add_trace(
            go.Scatter(
                x=signals['buy_signals']['timestamp'],
                y=signals['buy_signals']['price'],
                mode='markers',
                name='BUY Entry',
                marker=dict(
                    symbol='triangle-up',
                    size=15,
                    color='#00ff00',
                    line=dict(color='white', width=2)
                )
            ),
            row=1, col=1
        )
    
    # Add SELL signals
    if not signals['sell_signals'].empty:
        fig.add_trace(
            go.Scatter(
                x=signals['sell_signals']['timestamp'],
                y=signals['sell_signals']['price'],
                mode='markers',
                name='SELL Entry',
                marker=dict(
                    symbol='triangle-down',
                    size=15,
                    color='#ff0000',
                    line=dict(color='white', width=2)
                )
            ),
            row=1, col=1
        )
    
    # Add CLOSE signals
    if not signals['close_signals'].empty:
        fig.add_trace(
            go.Scatter(
                x=signals['close_signals']['timestamp'],
                y=signals['close_signals']['price'],
                mode='markers',
                name='Position Close',
                marker=dict(
                    symbol='x',
                    size=12,
                    color='#00bfff',
                    line=dict(color='white', width=2)
                )
            ),
            row=1, col=1
        )
    
    # MACD Indicator (subplot)
    if all(col in chart_data.columns for col in ['MACD', 'MACD_Signal', 'MACD_Histogram']):
        # MACD Line
        fig.add_trace(
            go.Scatter(
                x=chart_data['timestamp'],
                y=chart_data['MACD'],
                name='MACD',
                line=dict(color='#2196f3', width=2)
            ),
            row=2, col=1
        )
        
        # Signal Line
        fig.add_trace(
            go.Scatter(
                x=chart_data['timestamp'],
                y=chart_data['MACD_Signal'],
                name='Signal',
                line=dict(color='#ff9800', width=2)
            ),
            row=2, col=1
        )
        
        # Histogram
        colors = ['#00ff88' if val >= 0 else '#ff4444' for val in chart_data['MACD_Histogram']]
        fig.add_trace(
            go.Bar(
                x=chart_data['timestamp'],
                y=chart_data['MACD_Histogram'],
                name='Histogram',
                marker=dict(color=colors),
                opacity=0.6
            ),
            row=2, col=1
        )
        
        # Zero line
        fig.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.5, row=2, col=1)
    
    # Update layout
    fig.update_layout(
        height=800,
        showlegend=True,
        hovermode='x unified',
        xaxis_rangeslider_visible=False,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        )
    )
    
    fig.update_xaxes(title_text="Date", row=2, col=1)
    fig.update_yaxes(title_text="Price ($)", row=1, col=1)
    fig.update_yaxes(title_text="MACD Value", row=2, col=1)
    
    st.plotly_chart(fig, use_container_width=True)
    
    # Strategy Parameters Display
    st.markdown("---")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("### 📊 MACD Settings")
        st.code("""
Fast Period: 6
Slow Period: 10
Signal Period: 2
        """)
    
    with col2:
        st.markdown("### 📈 EMA Filter")
        st.code("""
Period: 168 bars
Timeframe: 4H
Duration: ~1 week
        """)
    
    with col3:
        st.markdown("### 🎯 Entry Rules")
        st.code("""
BUY: MACD > Signal + EMA
SELL: MACD < Signal + EMA
EXIT: Opposite signal
        """)
    
    # Trade Signal Summary
    st.markdown("---")
    st.subheader("📝 Recent Trade Signals on Chart")
    
    if not trades_df.empty:
        recent_trades = trades_df.head(10)[['timestamp', 'side', 'price', 'quantity', 'pnl', 'status']].copy()
        recent_trades['timestamp'] = recent_trades['timestamp'].dt.strftime('%Y-%m-%d %H:%M')
        recent_trades['price'] = recent_trades['price'].apply(lambda x: f"${x:,.2f}")
        recent_trades['quantity'] = recent_trades['quantity'].apply(lambda x: f"{x:.6f}")
        recent_trades['pnl'] = recent_trades['pnl'].apply(lambda x: f"${x:.2f}" if pd.notna(x) and x != 0 else "—")
        
        st.dataframe(recent_trades, use_container_width=True, height=400)
    else:
        st.info("No trades executed yet. Chart will show your strategy's signals once trading begins.")
    
    # Chart Controls
    st.markdown("---")
    st.markdown("### 🔧 Chart Tips")
    st.markdown("""
    - **Zoom**: Click and drag on chart
    - **Pan**: Hold Shift + drag
    - **Reset**: Double-click chart
    - **Toggle series**: Click legend items
    - **Hover**: See exact values
    - **Export**: Camera icon (top-right)
    """)

# ============================================================================
# ⚠️ RISK METRICS PAGE
# ============================================================================
elif page == "⚠️ Risk Metrics":
    st.title("⚠️ Risk Metrics")
    st.markdown("---")
    
    # Risk Metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Sharpe Ratio", f"{risk_metrics.get('sharpe_ratio', 0):.2f}")
        st.metric("Sortino Ratio", f"{risk_metrics.get('sortino_ratio', 0):.2f}")
    
    with col2:
        st.metric("Max Drawdown", f"${risk_metrics.get('max_drawdown', 0):.2f}")
        st.metric("Max DD %", f"{risk_metrics.get('max_drawdown_pct', 0):.2f}%")
    
    with col3:
        st.metric("Volatility", f"{risk_metrics.get('volatility', 0):.2f}%")
        st.metric("Downside Deviation", f"{risk_metrics.get('downside_deviation', 0):.2f}%")
    
    with col4:
        st.metric("Value at Risk (95%)", f"${risk_metrics.get('var_95', 0):.2f}")
        st.metric("Expected Shortfall", f"${risk_metrics.get('expected_shortfall', 0):.2f}")
    
    st.markdown("---")
    
    # Risk-Reward Chart
    st.subheader("📊 Risk-Reward Analysis")
    if not trades_df.empty:
        closed = trades_df[trades_df['status'] == 'CLOSED'].copy()
        if not closed.empty and 'pnl' in closed.columns:
            col1, col2 = st.columns(2)
            
            with col1:
                # Rolling volatility
                closed = closed.sort_values('timestamp')
                closed['returns'] = closed['pnl'].pct_change()
                closed['rolling_vol'] = closed['returns'].rolling(window=10).std() * np.sqrt(252) * 100
                
                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=closed['timestamp'],
                    y=closed['rolling_vol'],
                    mode='lines',
                    name='Rolling Volatility',
                    line=dict(color='orange', width=2)
                ))
                fig.update_layout(
                    height=400,
                    xaxis_title="Date",
                    yaxis_title="Volatility (%)",
                    hovermode='x unified'
                )
                st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                # Drawdown chart
                closed['cumulative_pnl'] = closed['pnl'].cumsum()
                closed['running_max'] = closed['cumulative_pnl'].cummax()
                closed['drawdown_pct'] = ((closed['cumulative_pnl'] - closed['running_max']) / closed['running_max'].abs()) * 100
                
                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=closed['timestamp'],
                    y=closed['drawdown_pct'],
                    mode='lines',
                    name='Drawdown %',
                    line=dict(color='red', width=2),
                    fill='tozeroy',
                    fillcolor='rgba(255, 0, 0, 0.2)'
                ))
                fig.update_layout(
                    height=400,
                    xaxis_title="Date",
                    yaxis_title="Drawdown (%)",
                    hovermode='x unified'
                )
                st.plotly_chart(fig, use_container_width=True)
    
    # Risk Exposure Table
    st.subheader("📋 Risk Exposure Summary")
    if not trades_df.empty:
        open_positions = trades_df[trades_df['status'] == 'OPEN']
        if not open_positions.empty:
            exposure_df = open_positions[['symbol', 'side', 'quantity', 'price', 'sl', 'tp']].copy()
            exposure_df['notional_value'] = (exposure_df['quantity'] * exposure_df['price']).apply(lambda x: f"${x:,.2f}")
            exposure_df['risk'] = ((exposure_df['price'] - exposure_df['sl']).abs() * exposure_df['quantity']).apply(lambda x: f"${x:,.2f}")
            st.dataframe(exposure_df, use_container_width=True)
        else:
            st.info("No open positions")

# ============================================================================
# 🔴 LIVE MONITORING PAGE
# ============================================================================
elif page == "🔴 Live Monitoring":
    st.title("🔴 Live Monitoring")
    st.markdown("---")
    
    # Auto-refresh
    auto_refresh = st.checkbox("Auto-refresh every 30s", value=False)
    if auto_refresh:
        st.markdown("🔄 Auto-refreshing...")
        import time
        time.sleep(30)
        st.rerun()
    
    # Current Status
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.subheader("📊 Current Positions")
        open_positions = trades_df[trades_df['status'] == 'OPEN'] if not trades_df.empty else pd.DataFrame()
        st.metric("Open Positions", len(open_positions))
        
        if not open_positions.empty:
            for idx, pos in open_positions.iterrows():
                with st.expander(f"{pos['symbol']} - {pos['side']}"):
                    st.write(f"**Entry Price:** ${pos['price']:,.2f}")
                    st.write(f"**Quantity:** {pos['quantity']:.4f}")
                    st.write(f"**Stop Loss:** ${pos['sl']:,.2f}")
                    st.write(f"**Take Profit:** ${pos['tp']:,.2f}")
                    st.write(f"**Unrealized P&L:** ${pos.get('unrealized_pnl', 0):.2f}")
    
    with col2:
        st.subheader("📈 Recent Activity")
        if not trades_df.empty:
            recent = trades_df.head(5)
            for idx, trade in recent.iterrows():
                status_emoji = "✅" if trade['status'] == 'CLOSED' else "🔵"
                st.write(f"{status_emoji} {trade['side']} @ ${trade['price']:,.2f}")
                st.caption(f"{trade['timestamp']}")
        else:
            st.info("No recent activity")
    
    with col3:
        st.subheader("💰 Today's Summary")
        if not trades_df.empty:
            today = datetime.now().date()
            trades_df['date'] = pd.to_datetime(trades_df['timestamp']).dt.date
            today_trades = trades_df[trades_df['date'] == today]
            
            st.metric("Trades Today", len(today_trades))
            if not today_trades.empty and 'pnl' in today_trades.columns:
                today_pnl = today_trades[today_trades['status'] == 'CLOSED']['pnl'].sum()
                st.metric("Today's P&L", f"${today_pnl:.2f}")
    
    st.markdown("---")
    
    # Log Events
    st.subheader("📜 Recent Log Events")
    if log_data:
        log_events = parse_log_events(log_data)
        if log_events:
            for event in log_events[:20]:  # Show last 20 events
                if 'ERROR' in event:
                    st.error(event)
                elif 'WARNING' in event:
                    st.warning(event)
                elif 'Position opened' in event or 'Position closed' in event:
                    st.success(event)
                else:
                    st.info(event)
        else:
            st.info("No recent log events")

# ============================================================================
# 📜 TRADE HISTORY PAGE
# ============================================================================
elif page == "📜 Trade History":
    st.title("📜 Complete Trade History")
    st.markdown("---")
    
    # Filters
    col1, col2, col3 = st.columns(3)
    
    with col1:
        status_filter = st.multiselect(
            "Status",
            options=['OPEN', 'CLOSED'],
            default=['OPEN', 'CLOSED']
        )
    
    with col2:
        side_filter = st.multiselect(
            "Side",
            options=['BUY', 'SELL', 'CLOSE'],
            default=['BUY', 'SELL', 'CLOSE']
        )
    
    with col3:
        date_range = st.date_input(
            "Date Range",
            value=(datetime.now().date() - timedelta(days=30), datetime.now().date()),
            max_value=datetime.now().date()
        )
    
    # Apply filters
    filtered_df = trades_df.copy()
    if not filtered_df.empty:
        filtered_df = filtered_df[filtered_df['status'].isin(status_filter)]
        filtered_df = filtered_df[filtered_df['side'].isin(side_filter)]
        
        if len(date_range) == 2:
            filtered_df['date'] = pd.to_datetime(filtered_df['timestamp']).dt.date
            filtered_df = filtered_df[
                (filtered_df['date'] >= date_range[0]) & 
                (filtered_df['date'] <= date_range[1])
            ]
    
    # Display table
    st.subheader(f"📊 {len(filtered_df)} Trades Found")
    if not filtered_df.empty:
        # Format for display
        display_df = filtered_df[[
            'timestamp', 'symbol', 'side', 'price', 'quantity', 
            'pnl', 'status', 'tx_signature'
        ]].copy()
        
        display_df['price'] = display_df['price'].apply(lambda x: f"${x:,.2f}")
        display_df['quantity'] = display_df['quantity'].apply(lambda x: f"{x:.6f}")
        display_df['pnl'] = display_df['pnl'].apply(lambda x: f"${x:.2f}" if pd.notna(x) and x != 0 else "—")
        
        st.dataframe(
            display_df,
            use_container_width=True,
            height=600,
            column_config={
                "timestamp": st.column_config.DatetimeColumn("Time", format="DD/MM/YY HH:mm"),
                "tx_signature": st.column_config.TextColumn("Tx Hash", width="small")
            }
        )
        
        # Download button
        csv = filtered_df.to_csv(index=False)
        st.download_button(
            label="📥 Download CSV",
            data=csv,
            file_name=f"trades_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv"
        )
    else:
        st.info("No trades match the selected filters")

# Footer
st.markdown("---")
st.markdown(
    """
    <div style='text-align: center; color: #666; padding: 20px;'>
        <p>🤖 Drift MACD Trading Bot Dashboard v1.0</p>
        <p>Strategy: BTC-PERP 4H MACD Momentum | Environment: Devnet</p>
    </div>
    """,
    unsafe_allow_html=True
)
