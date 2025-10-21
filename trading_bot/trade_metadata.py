"""
Enhanced trade logging constants and metadata
"""

# Bot version for tracking algorithm changes
BOT_VERSION = "2.0.0"

# Strategy identifiers
STRATEGIES = {
    'macd_btc_4h': {
        'id': 'macd_btc_4h_advanced',
        'name': 'MACD BTC 4H Advanced',
        'signal_type': 'momentum',
        'timeframe': '4H'
    },
    'ema_cross': {
        'id': 'ema_cross_v3',
        'name': 'EMA Cross V3',
        'signal_type': 'trend_following',
        'timeframe': '1H'
    }
}

# Fee constants for Drift Protocol
DRIFT_FEES = {
    'maker_fee_bps': 5,   # 0.05% = 5 basis points
    'taker_fee_bps': 6,   # 0.06% = 6 basis points
    'total_fee_bps': 11   # 0.11% total per side
}

# Trade status constants
TRADE_STATUS = {
    'OPEN': 'OPEN',
    'CLOSED': 'CLOSED',
    'CANCELLED': 'CANCELLED',
    'PARTIALLY_FILLED': 'PARTIALLY_FILLED'
}

# Signal types
SIGNAL_TYPES = {
    'MOMENTUM': 'momentum',
    'MEAN_REVERSION': 'mean_reversion',
    'BREAKOUT': 'breakout',
    'ARBITRAGE': 'arbitrage',
    'TREND_FOLLOWING': 'trend_following'
}

# Order types
ORDER_TYPES = {
    'MARKET': 'market',
    'LIMIT': 'limit',
    'REDUCE_ONLY': 'reduceOnly',
    'STOP_LOSS': 'stop_loss',
    'TAKE_PROFIT': 'take_profit'
}
