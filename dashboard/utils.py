"""
Utility functions for dashboard data processing
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
import re

def load_trades_data(trades_file='trades.csv'):
    """Load and parse trades CSV file"""
    try:
        # Get path relative to project root
        project_root = Path(__file__).parent.parent
        trades_path = project_root / trades_file
        
        if not trades_path.exists():
            return pd.DataFrame()
        
        df = pd.read_csv(trades_path)
        
        # Parse timestamp
        if 'timestamp' in df.columns:
            df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)
        
        # Ensure numeric columns
        numeric_cols = ['price', 'quantity', 'pnl', 'unrealized_pnl', 'sl', 'tp', 
                       'fee', 'slippage_bps', 'duration_seconds', 'leverage']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        
        return df
    
    except Exception as e:
        print(f"Error loading trades data: {e}")
        return pd.DataFrame()


def load_latest_log(log_dir='logs'):
    """Load the latest log file"""
    try:
        project_root = Path(__file__).parent.parent
        logs_path = project_root / log_dir
        
        if not logs_path.exists():
            return None
        
        # Find latest log file
        log_files = list(logs_path.glob('*.log'))
        if not log_files:
            return None
        
        latest_log = max(log_files, key=lambda x: x.stat().st_mtime)
        
        with open(latest_log, 'r') as f:
            return f.read()
    
    except Exception as e:
        print(f"Error loading log file: {e}")
        return None


def parse_log_events(log_content, max_events=50):
    """Parse log file and extract important events"""
    if not log_content:
        return []
    
    events = []
    lines = log_content.split('\n')
    
    # Parse recent events
    for line in lines[-max_events:]:
        if not line.strip():
            continue
        
        # Extract timestamp and message
        match = re.match(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}.*?) - (.*)', line)
        if match:
            timestamp, message = match.groups()
            events.append(f"[{timestamp}] {message}")
        else:
            events.append(line)
    
    return events


def calculate_performance_metrics(trades_df):
    """Calculate comprehensive performance metrics"""
    if trades_df.empty:
        return {
            'total_realized_pnl': 0,
            'total_unrealized_pnl': 0,
            'total_pnl_pct': 0,
            'win_rate': 0,
            'avg_win': 0,
            'avg_loss': 0,
            'profit_factor': 0,
            'best_trade': 0,
            'worst_trade': 0
        }
    
    # Filter closed trades for realized P&L
    closed_trades = trades_df[trades_df['status'] == 'CLOSED']
    
    # Total P&L
    total_realized_pnl = closed_trades['pnl'].sum() if not closed_trades.empty else 0
    total_unrealized_pnl = trades_df[trades_df['status'] == 'OPEN']['unrealized_pnl'].sum()
    
    # Win/Loss analysis
    if not closed_trades.empty and 'pnl' in closed_trades.columns:
        winning_trades = closed_trades[closed_trades['pnl'] > 0]
        losing_trades = closed_trades[closed_trades['pnl'] < 0]
        
        win_rate = (len(winning_trades) / len(closed_trades) * 100) if len(closed_trades) > 0 else 0
        avg_win = winning_trades['pnl'].mean() if not winning_trades.empty else 0
        avg_loss = losing_trades['pnl'].mean() if not losing_trades.empty else 0
        
        # Profit factor
        total_wins = winning_trades['pnl'].sum() if not winning_trades.empty else 0
        total_losses = abs(losing_trades['pnl'].sum()) if not losing_trades.empty else 0
        profit_factor = total_wins / total_losses if total_losses > 0 else 0
        
        best_trade = closed_trades['pnl'].max()
        worst_trade = closed_trades['pnl'].min()
    else:
        win_rate = 0
        avg_win = 0
        avg_loss = 0
        profit_factor = 0
        best_trade = 0
        worst_trade = 0
    
    # Calculate P&L percentage (rough estimate based on initial capital)
    # You can make this more accurate by tracking account equity
    total_pnl_pct = (total_realized_pnl / 1000) * 100 if total_realized_pnl != 0 else 0
    
    return {
        'total_realized_pnl': total_realized_pnl,
        'total_unrealized_pnl': total_unrealized_pnl,
        'total_pnl_pct': total_pnl_pct,
        'win_rate': win_rate,
        'avg_win': avg_win,
        'avg_loss': avg_loss,
        'profit_factor': profit_factor,
        'best_trade': best_trade,
        'worst_trade': worst_trade
    }


def calculate_risk_metrics(trades_df):
    """Calculate risk-adjusted performance metrics"""
    if trades_df.empty:
        return {
            'sharpe_ratio': 0,
            'sortino_ratio': 0,
            'max_drawdown': 0,
            'max_drawdown_pct': 0,
            'volatility': 0,
            'downside_deviation': 0,
            'var_95': 0,
            'expected_shortfall': 0
        }
    
    closed_trades = trades_df[trades_df['status'] == 'CLOSED']
    
    if closed_trades.empty or 'pnl' in closed_trades.columns and closed_trades['pnl'].std() == 0:
        return {
            'sharpe_ratio': 0,
            'sortino_ratio': 0,
            'max_drawdown': 0,
            'max_drawdown_pct': 0,
            'volatility': 0,
            'downside_deviation': 0,
            'var_95': 0,
            'expected_shortfall': 0
        }
    
    # Calculate returns
    pnl_series = closed_trades['pnl'].dropna()
    
    if len(pnl_series) < 2:
        return {
            'sharpe_ratio': 0,
            'sortino_ratio': 0,
            'max_drawdown': 0,
            'max_drawdown_pct': 0,
            'volatility': 0,
            'downside_deviation': 0,
            'var_95': 0,
            'expected_shortfall': 0
        }
    
    # Sharpe Ratio (assuming risk-free rate = 0)
    mean_return = pnl_series.mean()
    std_return = pnl_series.std()
    sharpe_ratio = mean_return / std_return if std_return > 0 else 0
    
    # Sortino Ratio (downside deviation)
    downside_returns = pnl_series[pnl_series < 0]
    downside_deviation = downside_returns.std() if not downside_returns.empty else 0
    sortino_ratio = mean_return / downside_deviation if downside_deviation > 0 else 0
    
    # Maximum Drawdown
    cumulative_pnl = pnl_series.cumsum()
    running_max = cumulative_pnl.cummax()
    drawdown = cumulative_pnl - running_max
    max_drawdown = drawdown.min()
    max_drawdown_pct = (max_drawdown / running_max.max() * 100) if running_max.max() > 0 else 0
    
    # Volatility (annualized)
    volatility = std_return * np.sqrt(252)  # Assuming daily trades, annualize
    
    # Value at Risk (95% confidence)
    var_95 = np.percentile(pnl_series, 5)
    
    # Expected Shortfall (CVaR)
    expected_shortfall = pnl_series[pnl_series <= var_95].mean()
    
    return {
        'sharpe_ratio': sharpe_ratio,
        'sortino_ratio': sortino_ratio,
        'max_drawdown': max_drawdown,
        'max_drawdown_pct': abs(max_drawdown_pct),
        'volatility': volatility,
        'downside_deviation': downside_deviation,
        'var_95': var_95,
        'expected_shortfall': expected_shortfall
    }


def get_trade_statistics(trades_df):
    """Get general trade statistics"""
    if trades_df.empty:
        return {
            'total_trades': 0,
            'closed_trades': 0,
            'open_positions': 0,
            'long_trades': 0,
            'short_trades': 0,
            'winning_trades': 0,
            'losing_trades': 0,
            'avg_position_size': 0,
            'avg_hold_time_hours': 0
        }
    
    total_trades = len(trades_df)
    closed_trades = len(trades_df[trades_df['status'] == 'CLOSED'])
    open_positions = len(trades_df[trades_df['status'] == 'OPEN'])
    
    # Long vs Short (based on entry side)
    long_trades = len(trades_df[trades_df['side'] == 'BUY'])
    short_trades = len(trades_df[trades_df['side'] == 'SELL'])
    
    # Winning vs Losing
    closed = trades_df[trades_df['status'] == 'CLOSED']
    if not closed.empty and 'pnl' in closed.columns:
        winning_trades = len(closed[closed['pnl'] > 0])
        losing_trades = len(closed[closed['pnl'] < 0])
    else:
        winning_trades = 0
        losing_trades = 0
    
    # Average position size
    avg_position_size = trades_df['quantity'].mean() if 'quantity' in trades_df.columns else 0
    
    # Average hold time
    if 'duration_seconds' in trades_df.columns:
        avg_hold_time_seconds = closed['duration_seconds'].mean() if not closed.empty else 0
        avg_hold_time_hours = avg_hold_time_seconds / 3600
    else:
        avg_hold_time_hours = 0
    
    return {
        'total_trades': total_trades,
        'closed_trades': closed_trades,
        'open_positions': open_positions,
        'long_trades': long_trades,
        'short_trades': short_trades,
        'winning_trades': winning_trades,
        'losing_trades': losing_trades,
        'avg_position_size': avg_position_size,
        'avg_hold_time_hours': avg_hold_time_hours
    }


def format_currency(value):
    """Format value as currency"""
    return f"${value:,.2f}" if pd.notna(value) else "$0.00"


def format_percentage(value):
    """Format value as percentage"""
    return f"{value:.2f}%" if pd.notna(value) else "0.00%"


def get_trade_pairs(trades_df):
    """Match OPEN and CLOSE trades into pairs for analysis"""
    if trades_df.empty:
        return pd.DataFrame()
    
    pairs = []
    open_trades = trades_df[trades_df['side'].isin(['BUY', 'SELL'])].copy()
    close_trades = trades_df[trades_df['side'] == 'CLOSE'].copy()
    
    for idx, close_trade in close_trades.iterrows():
        # Find corresponding open trade (closest before close)
        potential_opens = open_trades[open_trades['timestamp'] < close_trade['timestamp']]
        if not potential_opens.empty:
            open_trade = potential_opens.iloc[-1]
            
            pairs.append({
                'entry_time': open_trade['timestamp'],
                'exit_time': close_trade['timestamp'],
                'entry_side': open_trade['side'],
                'entry_price': open_trade['price'],
                'exit_price': close_trade['price'],
                'quantity': close_trade['quantity'],
                'pnl': close_trade['pnl'],
                'duration_hours': (close_trade['timestamp'] - open_trade['timestamp']).total_seconds() / 3600
            })
    
    return pd.DataFrame(pairs)


def calculate_macd(df, fast=6, slow=10, signal=2):
    """
    Calculate MACD indicator
    
    Args:
        df: DataFrame with 'close' prices
        fast: Fast EMA period (default 6)
        slow: Slow EMA period (default 10)
        signal: Signal line period (default 2)
    
    Returns:
        DataFrame with MACD, Signal, and Histogram columns
    """
    if df.empty or 'close' not in df.columns:
        return df
    
    # Calculate EMAs
    ema_fast = df['close'].ewm(span=fast, adjust=False).mean()
    ema_slow = df['close'].ewm(span=slow, adjust=False).mean()
    
    # MACD line
    df['MACD'] = ema_fast - ema_slow
    
    # Signal line
    df['MACD_Signal'] = df['MACD'].ewm(span=signal, adjust=False).mean()
    
    # Histogram
    df['MACD_Histogram'] = df['MACD'] - df['MACD_Signal']
    
    return df


def calculate_ema(df, period=168):
    """
    Calculate Exponential Moving Average
    
    Args:
        df: DataFrame with 'close' prices
        period: EMA period (default 168)
    
    Returns:
        DataFrame with EMA column
    """
    if df.empty or 'close' not in df.columns:
        return df
    
    df[f'EMA_{period}'] = df['close'].ewm(span=period, adjust=False).mean()
    
    return df


def get_historical_data_mock(symbol='BTC-PERP', timeframe='4h', periods=200):
    """
    Mock function to generate sample historical data for charting
    In production, this would fetch from Drift/Pyth oracles
    
    Args:
        symbol: Trading symbol
        timeframe: Timeframe (e.g., '4h')
        periods: Number of periods to generate
    
    Returns:
        DataFrame with OHLCV data
    """
    # Generate sample data (replace with actual API call in production)
    from datetime import timedelta
    
    end_time = datetime.now()
    start_time = end_time - timedelta(hours=4 * periods)
    
    # Create date range
    date_range = pd.date_range(start=start_time, end=end_time, periods=periods)
    
    # Generate realistic BTC price data (mock)
    np.random.seed(42)
    base_price = 112000
    prices = base_price + np.cumsum(np.random.randn(periods) * 500)
    
    df = pd.DataFrame({
        'timestamp': date_range,
        'open': prices + np.random.randn(periods) * 100,
        'high': prices + np.abs(np.random.randn(periods) * 200),
        'low': prices - np.abs(np.random.randn(periods) * 200),
        'close': prices,
        'volume': np.random.randint(100, 1000, periods)
    })
    
    # Calculate indicators
    df = calculate_macd(df, fast=6, slow=10, signal=2)
    df = calculate_ema(df, period=168)
    
    return df


def get_trade_signals_for_chart(trades_df):
    """
    Extract trade signals for chart overlay
    
    Args:
        trades_df: DataFrame from trades.csv
    
    Returns:
        Dict with buy_signals, sell_signals, close_signals DataFrames
    """
    if trades_df.empty:
        return {
            'buy_signals': pd.DataFrame(),
            'sell_signals': pd.DataFrame(),
            'close_signals': pd.DataFrame()
        }
    
    buy_signals = trades_df[trades_df['side'] == 'BUY'].copy()
    sell_signals = trades_df[trades_df['side'] == 'SELL'].copy()
    close_signals = trades_df[trades_df['side'] == 'CLOSE'].copy()
    
    return {
        'buy_signals': buy_signals,
        'sell_signals': sell_signals,
        'close_signals': close_signals
    }
