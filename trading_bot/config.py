# import os
# from dotenv import load_dotenv
# from alpaca.data.timeframe import TimeFrameUnit

# load_dotenv()

# API_KEY = os.getenv("API_KEY")
# SECRET_KEY = os.getenv("SECRET_KEY")

# LIST_OF_TICKERS = ["AAVE/USD", "ETH/USD", "SOL/USD"]

# # Timeframe and strategy configs
# TIME_FRAME = 1
# TIME_FRAME_UNIT = TimeFrameUnit.Minute
# DAYS = 20
# START_HOUR, START_MIN = 7, 1
# END_HOUR, END_MIN = 9, 35
# TIME_ZONE = "America/New_York"
# STRATEGY_NAME = "crypto_supertrend_ema_strategy"
# STOP_PERC = 2

"""
Configuration file for the Drift Protocol trading bot
"""
import os
from datetime import timezone, timedelta
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Solana & Drift Configuration
SOLANA_RPC_URL = os.getenv("SOLANA_RPC_URL", "https://api.devnet.solana.com")
RPC_URL = os.getenv("RPC_URL", SOLANA_RPC_URL)  # Primary RPC (Helius preferred)
PRIVATE_KEY = os.getenv("PRIVATE_KEY")  # Base58 encoded private key or path to keypair file
DRIFT_ENV = os.getenv("DRIFT_ENV", "devnet")  # "devnet" or "mainnet"

# RPC Fallback Configuration - Try these in order if one fails
RPC_ENDPOINTS = [
    RPC_URL,  # Primary (from .env)
    SOLANA_RPC_URL,  # Secondary (from .env)
    "https://rpc-devnet.helius.xyz",  # Free public Helius
    "https://api.devnet.solana.com",  # Public Solana devnet
]

# RPC Connection Settings
RPC_TIMEOUT = 30.0  # Initial timeout in seconds
RPC_MAX_RETRIES = 3  # Retries per endpoint

# Trading Parameters
# Drift Protocol Perpetual Markets (devnet)
PERP_MARKETS = [
    {"symbol": "SOL-PERP", "market_index": 0},
    {"symbol": "BTC-PERP", "market_index": 1}, 
    {"symbol": "ETH-PERP", "market_index": 2}
]

# Drift Protocol Spot Markets (devnet) 
SPOT_MARKETS = [
    {"symbol": "USDC", "market_index": 0},
    {"symbol": "SOL", "market_index": 1}
]

# Timezone Configuration
TIME_ZONE = 'UTC'

# Timezone Configuration - Centralized timezone control
# You can change this to any timezone (e.g., 'US/Eastern', 'Europe/London', 'Asia/Tokyo')
# All datetime operations throughout the bot will use this timezone
def get_timezone():
    """Get the configured timezone object"""
    if TIME_ZONE.upper() == 'UTC':
        return timezone.utc
    else:
        # For non-UTC timezones, you can extend this with pytz or zoneinfo
        # For now, supporting UTC and basic offset formats
        try:
            # Try to parse as UTC offset (e.g., '+05:00', '-08:00')
            if TIME_ZONE.startswith(('+', '-')):
                hours, minutes = TIME_ZONE[1:].split(':')
                offset = timedelta(hours=int(hours), minutes=int(minutes))
                if TIME_ZONE.startswith('-'):
                    offset = -offset
                return timezone(offset)
            else:
                # Default to UTC for unsupported timezone strings
                print(f"Warning: Timezone '{TIME_ZONE}' not supported, using UTC")
                return timezone.utc
        except:
            print(f"Warning: Invalid timezone format '{TIME_ZONE}', using UTC")
            return timezone.utc

# Create the timezone object once
TIMEZONE = get_timezone()

# ================================
# MACD MOMENTUM STRATEGY CONFIG  
# ================================

# Strategy Selection
STRATEGY_NAME = 'drift_macd_momentum_strategy'

# MACD Parameters (BTC-PERP 4H Timeframe Only - Optimized: 6, 10, 2, 168)
MACD_TARGET_SYMBOL = "BTC-PERP"  # Only trade BTC perpetual
MACD_TIMEFRAME = 240             # 4-hour timeframe in minutes
MACD_FAST_PERIOD = 6             # Fast EMA period
MACD_SLOW_PERIOD = 10            # Slow EMA period  
MACD_SIGNAL_PERIOD = 2           # Signal line period
EMA_FILTER_PERIOD = 168          # Long-term trend filter (168 = 4h * 42 = 1 week)

# MACD Strategy Specific Parameters
MACD_STOP_BUFFER = 5             # Stop loss buffer in USD

# === FINAL 4H MACD STRATEGY CONFIG (Balanced Quant Setup) ===

# --- RISK MANAGEMENT PARAMETERS ---
INITIAL_STOP_ATR_MULTIPLIER = 2.8       # Balanced initial stop (not too tight, not loose)
TRAILING_STOP_ATR_MULTIPLIER = 4.0      # Tight enough to lock profit, wide enough for trends
TRAILING_ACTIVATION_ATR = 3.0            # Activate trailing once profit > 3.0x ATR
TAKE_PROFIT_ATR_MULTIPLIER = 6.0        # Target 2.2x risk-reward ratio
MAX_DRAWDOWN_PCT = 0.10                 # Account-level emergency cutoff at 10%

# Position sizing
POSITION_PCT = 0.30  # Use 30% of available balance per trade
MAX_POSITION_PCT = 0.30  # Maximum position size (same as POSITION_PCT for risk manager)
LEVERAGE_MULTIPLIER = 1.0  # Use 2x leverage (double the exposure)

# --- RISK MANAGEMENT BEHAVIOR ---
STOP_LOSS_BUFFER = 5                    # Small slippage allowance
TRAILING_STOP = True                    # Enable dynamic profit protection
MIN_SIGNAL_STRENGTH = 0.20              # Filter weak MACD crossovers
MIN_TRADE_INTERVAL = 480                # Wait 8 hours between trades (2 bars)
MIN_POSITION_HOLD_TIME = 480            # Hold at least 6 hours before eligible to close

# --- ADVANCED HOLD TIME CONTROLS ---
FLEXIBLE_HOLD_TIME = False               # Allow configurable hold times based on market conditions
MIN_HOLD_TIME_FLEXIBLE = 360            # Minimum 6 hours for flexible mode (less strict)
STRONG_REVERSAL_THRESHOLD = 0.50        # MACD difference threshold for early reversal override
ENABLE_EARLY_REVERSAL_OVERRIDE = True   # Allow strong signals to override hold time

# --- TIMEFRAMES ---
PRIMARY_TIMEFRAME = '4h'                # Main trading timeframe
CONFIRM_TIMEFRAME = '4h'                 # Confirmation layer for entry validation
PRIMARY_PERIODS = 100                    # MACD + EMA smoothing depth
CONFIRM_PERIODS = 100                    # Trend validation depth

# --- SAFETY SETTINGS ---
SAFETY_MARGIN = 0.8                     # Reserve 20% capital buffer
CASH_ALLOCATION_MODE = 'full'           # Use full balance (within safety margin)

# File Paths
TRADES_FILE = "trades.csv"
ORDERS_FILE = "orders.csv"

# Execution Settings
STRATEGY_CHECK_INTERVAL = 60  # Check every minute
DEBUG = True

# Drift Protocol Settings
SUB_ACCOUNT_ID = 0  # Default subaccount
TX_COMPUTE_UNITS = 200_000
TX_COMPUTE_UNIT_PRICE = 10_000

# ---------------------------------------------------
# Symbol Normalization Helper for Drift
# ---------------------------------------------------
def normalize_symbol(symbol: str) -> str:
    """
    Normalize ticker symbols for Drift Protocol.
    Example: "SOL-PERP" -> "SOL-PERP", "BTC/USD" -> "BTC-PERP"
    """
    if symbol.endswith("-PERP"):
        return symbol
    if "/" in symbol:
        base = symbol.split("/")[0]
        return f"{base}-PERP"
    return symbol

def get_market_index_by_symbol(symbol: str) -> int:
    """
    Get market index for a given symbol
    """
    normalized = normalize_symbol(symbol)
    
    # Check perpetual markets first
    for market in PERP_MARKETS:
        if market["symbol"] == normalized:
            return market["market_index"]
    
    # Check spot markets
    for market in SPOT_MARKETS:
        if market["symbol"] == normalized:
            return market["market_index"]
    
    raise ValueError(f"Market {symbol} not found in configuration")

