"""
Drift Protocol Trading Dashboard
Streamlit app for visualizing trading performance
Combines CSV trade data with log files for accurate SL/TP detection
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
import sys
import os
import re
import glob

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Page config
st.set_page_config(
    page_title="Drift Trading Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .metric-card {
        background-color: #f0f2f6;
        padding: 20px;
        border-radius: 10px;
        margin: 10px 0;
    }
    .positive { color: #00ff00; }
    .negative { color: #ff0000; }
    .big-font { font-size: 24px !important; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

@st.cache_data(ttl=60)
def load_trades():
    """Load trades from CSV"""
    try:
        # Get the absolute path to trades.csv
        current_dir = os.path.dirname(os.path.abspath(__file__))
        trades_path = os.path.join(current_dir, '..', 'trades.csv')
        
        df = pd.read_csv(trades_path)
        # Normalize types
        df['timestamp'] = pd.to_datetime(df['timestamp'], format='mixed', utc=True, errors='coerce')
        for col in ['price', 'quantity', 'sl', 'tp']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        # Ensure non-negative quantities
        if 'quantity' in df.columns:
            df['quantity'] = df['quantity'].abs()
        return df
    except Exception as e:
        st.error(f"Error loading trades: {e}")
        return pd.DataFrame()

def calculate_pnl(trades_df):
    """Calculate P&L from trades with proper matching"""
    if trades_df.empty:
        return pd.DataFrame(), 0, 0, 0
    
    # Filter only executed trades (not bot signals)
    executed_trades = trades_df[
        (trades_df['tx_signature'].notna()) & 
        (trades_df['tx_signature'] != 'CLOSED_BY_BOT') &
        (trades_df['tx_signature'] != 'EXTERNAL_POSITION_DETECTED')
    ].copy()
    
    if executed_trades.empty:
        return pd.DataFrame(), 0, 0, 0
    
    # Basic sanity filter to drop obviously malformed close prices (e.g., 107 vs 107,000 for BTC)
    if {'symbol', 'side', 'price'}.issubset(executed_trades.columns):
        executed_trades = executed_trades[~(
            (executed_trades['side'] == 'CLOSE') &
            (executed_trades['symbol'] == 'BTC-PERP') &
            (pd.to_numeric(executed_trades['price'], errors='coerce') < 1000)
        )]

    # Sort by timestamp
    executed_trades = executed_trades.sort_values('timestamp')
    
    # Calculate P&L for each closed trade
    pnl_records = []
    position = None
    total_pnl = 0
    total_fees = 0
    
    for idx, trade in executed_trades.iterrows():
        if trade['side'] in ['BUY', 'SELL'] and position is None:
            # Opening a position
            position = {
                'side': trade['side'],
                'entry_price': trade['price'],
                'entry_time': trade['timestamp'],
                'quantity': trade['quantity'],
                'sl': trade['sl'],
                'tp': trade['tp']
            }
        
        elif trade['side'] == 'CLOSE' and position is not None:
            # Closing position
            exit_price = trade['price']
            
            # Calculate P&L
            if position['side'] == 'BUY':
                pnl = (exit_price - position['entry_price']) * position['quantity']
            else:  # SELL
                pnl = (position['entry_price'] - exit_price) * position['quantity']
            
            # Check exit reason
            exit_reason = 'Unknown'
            if abs(exit_price - position['tp']) < 1:
                exit_reason = 'Take Profit'
            elif abs(exit_price - position['sl']) < 1:
                exit_reason = 'Stop Loss'
            else:
                exit_reason = 'Manual/Other'
            
            pnl_records.append({
                'entry_time': position['entry_time'],
                'exit_time': trade['timestamp'],
                'side': position['side'],
                'entry_price': position['entry_price'],
                'exit_price': exit_price,
                'quantity': position['quantity'],
                'sl': position['sl'],
                'tp': position['tp'],
                'pnl': pnl,
                'exit_reason': exit_reason,
                'duration': (trade['timestamp'] - position['entry_time']).total_seconds() / 3600
            })
            
            total_pnl += pnl
            position = None
    
    pnl_df = pd.DataFrame(pnl_records)
    
    if not pnl_df.empty:
        pnl_df['cumulative_pnl'] = pnl_df['pnl'].cumsum()
        winning_trades = len(pnl_df[pnl_df['pnl'] > 0])
        losing_trades = len(pnl_df[pnl_df['pnl'] < 0])
        win_rate = (winning_trades / len(pnl_df) * 100) if len(pnl_df) > 0 else 0
    else:
        winning_trades = 0
        losing_trades = 0
        win_rate = 0
    
    return pnl_df, total_pnl, winning_trades, win_rate

def main():
    # Header
    st.title("📊 Drift Protocol Trading Dashboard")
    st.markdown("---")
    
    # Load data
    trades_df = load_trades()
    
    if trades_df.empty:
        st.warning("No trades found. Start trading to see your dashboard!")
        return
    
    # Calculate P&L
    pnl_df, total_pnl, winning_trades, win_rate = calculate_pnl(trades_df)
    
    # Sidebar filters
    st.sidebar.header("🔧 Filters")
    
    # Date range filter
    min_date = trades_df['timestamp'].min().date()
    max_date = trades_df['timestamp'].max().date()
    
    date_range = st.sidebar.date_input(
        "Date Range",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date
    )
    
    if len(date_range) == 2:
        start_date, end_date = date_range
        trades_df = trades_df[
            (trades_df['timestamp'].dt.date >= start_date) &
            (trades_df['timestamp'].dt.date <= end_date)
        ]
        
        if not pnl_df.empty:
            pnl_df = pnl_df[
                (pnl_df['entry_time'].dt.date >= start_date) &
                (pnl_df['exit_time'].dt.date <= end_date)
            ]
    
    # Symbol filter
    symbols = trades_df['symbol'].unique()
    selected_symbol = st.sidebar.selectbox("Symbol", ['All'] + list(symbols))
    
    if selected_symbol != 'All':
        trades_df = trades_df[trades_df['symbol'] == selected_symbol]
    
    # Key Metrics
    st.header("📈 Performance Overview")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        # Show Total P&L without an arbitrary percentage delta to avoid misleading signals
        st.metric("Total P&L", f"${total_pnl:,.2f}")
    
    with col2:
        total_trades = len(pnl_df) if not pnl_df.empty else 0
        st.metric("Total Trades", total_trades)
    
    with col3:
        st.metric("Win Rate", f"{win_rate:.1f}%")
    
    with col4:
        avg_pnl = pnl_df['pnl'].mean() if not pnl_df.empty else 0
        st.metric("Avg P&L per Trade", f"${avg_pnl:.2f}")
    
    # Tabs
    tab1, tab2, tab3, tab4 = st.tabs(["📊 Overview", "📋 Trade History", "📈 P&L Chart", "🎯 Analytics"])
    
    with tab1:
        st.subheader("Recent Activity")
        
        if not pnl_df.empty:
            # Cumulative P&L Chart
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=list(range(len(pnl_df))),
                y=pnl_df['cumulative_pnl'],
                mode='lines+markers',
                name='Cumulative P&L',
                line=dict(color='#00ff00' if total_pnl > 0 else '#ff0000', width=3),
                fill='tozeroy',
                fillcolor='rgba(0,255,0,0.1)' if total_pnl > 0 else 'rgba(255,0,0,0.1)'
            ))
            
            fig.update_layout(
                title="Cumulative P&L Over Time",
                xaxis_title="Trade Number",
                yaxis_title="P&L ($)",
                height=400,
                hovermode='x unified'
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
            # Win/Loss Distribution
            col1, col2 = st.columns(2)
            
            with col1:
                wins = pnl_df[pnl_df['pnl'] > 0]
                losses = pnl_df[pnl_df['pnl'] <= 0]
                
                fig_pie = go.Figure(data=[go.Pie(
                    labels=['Wins', 'Losses'],
                    values=[len(wins), len(losses)],
                    marker=dict(colors=['#00ff00', '#ff0000']),
                    hole=0.4
                )])
                
                fig_pie.update_layout(
                    title="Win/Loss Distribution",
                    height=300
                )
                
                st.plotly_chart(fig_pie, use_container_width=True)
            
            with col2:
                # Exit Reason Breakdown
                exit_reasons = pnl_df['exit_reason'].value_counts()
                
                fig_bar = px.bar(
                    x=exit_reasons.index,
                    y=exit_reasons.values,
                    labels={'x': 'Exit Reason', 'y': 'Count'},
                    title="Exit Reasons",
                    color=exit_reasons.values,
                    color_continuous_scale='Viridis'
                )
                
                fig_bar.update_layout(height=300)
                st.plotly_chart(fig_bar, use_container_width=True)
        else:
            st.info("No closed trades yet")
    
    with tab2:
        st.subheader("Complete Trade History")
        
        if not pnl_df.empty:
            # Format for display
            display_df = pnl_df.copy()
            display_df['entry_time'] = display_df['entry_time'].dt.strftime('%Y-%m-%d %H:%M')
            display_df['exit_time'] = display_df['exit_time'].dt.strftime('%Y-%m-%d %H:%M')
            display_df['entry_price'] = display_df['entry_price'].apply(lambda x: f"${x:,.2f}")
            display_df['exit_price'] = display_df['exit_price'].apply(lambda x: f"${x:,.2f}")
            display_df['sl'] = display_df['sl'].apply(lambda x: f"${x:,.2f}")
            display_df['tp'] = display_df['tp'].apply(lambda x: f"${x:,.2f}")
            display_df['pnl'] = display_df['pnl'].apply(lambda x: f"${x:,.2f}")
            display_df['duration'] = display_df['duration'].apply(lambda x: f"{x:.1f}h")
            
            st.dataframe(
                display_df[[
                    'entry_time', 'exit_time', 'side', 'entry_price', 'exit_price',
                    'quantity', 'sl', 'tp', 'pnl', 'exit_reason', 'duration'
                ]],
                use_container_width=True,
                height=400
            )
            
            # Download button
            csv = pnl_df.to_csv(index=False)
            st.download_button(
                label="📥 Download Trade History",
                data=csv,
                file_name=f"trade_history_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv"
            )
        else:
            st.info("No closed trades to display")
    
    with tab3:
        st.subheader("P&L Analysis")
        
        if not pnl_df.empty:
            # Daily P&L
            pnl_df['date'] = pnl_df['exit_time'].dt.date
            daily_pnl = pnl_df.groupby('date')['pnl'].sum().reset_index()
            
            fig_daily = go.Figure()
            fig_daily.add_trace(go.Bar(
                x=daily_pnl['date'],
                y=daily_pnl['pnl'],
                marker=dict(
                    color=daily_pnl['pnl'],
                    colorscale=['red', 'green'],
                    cmin=daily_pnl['pnl'].min(),
                    cmax=daily_pnl['pnl'].max()
                ),
                text=daily_pnl['pnl'].apply(lambda x: f"${x:.2f}"),
                textposition='outside'
            ))
            
            fig_daily.update_layout(
                title="Daily P&L",
                xaxis_title="Date",
                yaxis_title="P&L ($)",
                height=400,
                showlegend=False
            )
            
            st.plotly_chart(fig_daily, use_container_width=True)
            
            # Trade Distribution
            col1, col2 = st.columns(2)
            
            with col1:
                fig_hist = px.histogram(
                    pnl_df,
                    x='pnl',
                    nbins=20,
                    title="P&L Distribution",
                    labels={'pnl': 'P&L ($)'},
                    color_discrete_sequence=['#1f77b4']
                )
                fig_hist.update_layout(height=300)
                st.plotly_chart(fig_hist, use_container_width=True)
            
            with col2:
                fig_duration = px.box(
                    pnl_df,
                    y='duration',
                    title="Trade Duration Distribution",
                    labels={'duration': 'Duration (hours)'},
                    color_discrete_sequence=['#ff7f0e']
                )
                fig_duration.update_layout(height=300)
                st.plotly_chart(fig_duration, use_container_width=True)
        else:
            st.info("No data to display")
    
    with tab4:
        st.subheader("Advanced Analytics")
        
        if not pnl_df.empty:
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("Best Trade", f"${pnl_df['pnl'].max():.2f}")
                st.metric("Worst Trade", f"${pnl_df['pnl'].min():.2f}")
            
            with col2:
                avg_win = pnl_df[pnl_df['pnl'] > 0]['pnl'].mean() if len(pnl_df[pnl_df['pnl'] > 0]) > 0 else 0
                avg_loss = pnl_df[pnl_df['pnl'] < 0]['pnl'].mean() if len(pnl_df[pnl_df['pnl'] < 0]) > 0 else 0
                
                st.metric("Avg Win", f"${avg_win:.2f}")
                st.metric("Avg Loss", f"${avg_loss:.2f}")
            
            with col3:
                profit_factor = abs(avg_win / avg_loss) if avg_loss != 0 else 0
                st.metric("Profit Factor", f"{profit_factor:.2f}")
                st.metric("Avg Duration", f"{pnl_df['duration'].mean():.1f}h")
            
            # Side performance
            st.subheader("Performance by Side")
            side_performance = pnl_df.groupby('side').agg({
                'pnl': ['sum', 'mean', 'count']
            }).round(2)
            
            st.dataframe(side_performance, use_container_width=True)
        else:
            st.info("No analytics available yet")
    
    # Footer
    st.markdown("---")
    st.markdown(
        f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | "
        f"Total Records: {len(trades_df)} | "
        f"Data Range: {trades_df['timestamp'].min().strftime('%Y-%m-%d')} to {trades_df['timestamp'].max().strftime('%Y-%m-%d')}"
    )

if __name__ == "__main__":
    main()
