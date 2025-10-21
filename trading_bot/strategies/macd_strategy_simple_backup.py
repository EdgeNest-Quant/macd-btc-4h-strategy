"""
MACD Momentum Strategy for Drift Protocol
Adapted from optimized 2x leverage MACD strategy for BTC perpetual futures
"""
import asyncio
import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional
import ta

from ..config import (TIMEZONE, MACD_TARGET_SYMBOL, MACD_TIMEFRAME, MACD_FAST_PERIOD, 
                    MACD_SLOW_PERIOD, MACD_SIGNAL_PERIOD, EMA_FILTER_PERIOD, 
                    MACD_POSITION_PCT, MACD_STOP_BUFFER, MIN_SIGNAL_STRENGTH, PERP_MARKETS)
from ..logger import logger
from ..data.data_handler import DriftDataHandler
from ..broker.execution import DriftOrderExecutor 
from ..risk.risk_manager import DriftRiskManager
from ..portfolio.portfolio_tracker import DriftPortfolioTracker


class DriftMACDStrategy:
    """
    MACD Momentum Strategy with 2x effective leverage for Drift Protocol
    
    Strategy Logic:
    - Primary: MACD crossover signals (6,10,2 parameters)
    - Filter: 168-period EMA for trend confirmation  
    - Entry: MACD crosses signal line with price above/below EMA
    - Exit: Opposite crossover or trailing stop triggered
    - Risk: Dynamic position sizing with 2x effective leverage
    """
    
    def __init__(self, data_handler: DriftDataHandler, executor: DriftOrderExecutor, 
                 risk_manager: DriftRiskManager, portfolio: DriftPortfolioTracker):
        self.data_handler = data_handler
        self.executor = executor
        self.risk_manager = risk_manager
        self.portfolio = portfolio
        
        # MACD Strategy Configuration
        self.config = {
            'fast_period': MACD_FAST_PERIOD,
            'slow_period': MACD_SLOW_PERIOD,
            'signal_period': MACD_SIGNAL_PERIOD,
            'ema_filter': EMA_FILTER_PERIOD,
            'position_pct': MACD_POSITION_PCT,
            'stop_buffer': MACD_STOP_BUFFER,
            'min_signal_strength': 0.1,  # Default minimum signal strength
        }        # Track current positions and last trade time
        self.positions = {}
        self.last_trade_time = {}
        self.trailing_stops = {}
        
        logger.info(f"MACD Strategy initialized with config: {self.config}")
    
    async def initialize(self):
        """Initialize the strategy (required by main bot)"""
        try:
            logger.info("Initializing MACD strategy...")
            # Any async initialization can go here
            logger.info("MACD strategy initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing MACD strategy: {e}")
            raise
    
    async def close_all_positions(self):
        """Close all open positions (required by main bot)"""
        try:
            logger.info("Closing all MACD strategy positions...")
            closed_count = 0
            
            for symbol in list(self.positions.keys()):
                try:
                    # Get current positions from executor
                    positions = await self.executor.get_positions()
                    
                    for position in positions:
                        if position.get('market_index') is not None:
                            # Close the position
                            await self.executor.close_position(position['market_index'])
                            closed_count += 1
                            logger.info(f"Closed position for market index {position['market_index']}")
                            
                except Exception as e:
                    logger.warning(f"Error closing position for {symbol}: {e}")
            
            # Clear internal position tracking
            self.positions.clear()
            logger.info(f"All positions closed. Total closed: {closed_count}")
            
        except Exception as e:
            logger.error(f"Error closing all positions: {e}")
    
    async def cleanup(self):
        """Cleanup strategy resources"""
        try:
            await self.close_all_positions()
            logger.info("MACD strategy cleanup completed")
        except Exception as e:
            logger.error(f"Error during strategy cleanup: {e}")
    
    async def run_strategy(self, data_handler, executor, risk_manager, portfolio_tracker):
        """
        Execute MACD momentum strategy on BTC-PERP only with 4-hour timeframe
        """
        logger.debug("=== MACD Strategy Execution Started (BTC-PERP 4H) ===")
        
        try:
            # Get account balance
            balance = await executor.get_account_balance()
            logger.debug(f"Account balance: Free collateral = {balance:.2f} USD")
            
            signals_generated = 0
            trades_executed = 0
            
            # Process only BTC-PERP market
            symbol = MACD_TARGET_SYMBOL
            market_index = next((m["market_index"] for m in PERP_MARKETS if m["symbol"] == symbol), 1)  # Default to 1 for BTC-PERP
                symbol = market['symbol']
                market_index = market['market_index']
                
                try:
                    logger.debug(f"Analyzing {symbol} (market index: {market_index})...")
                    
                    # Generate multi-timeframe signals
                    signals = await self.generate_signals(symbol, timeframes)
                    
                    if not signals:
                        logger.warning(f"No signals generated for {symbol}")
                        continue
                    
                    # Check current position
                    current_position = await self.executor.get_position_info(market_index)
                    has_position = current_position is not None
                    
                    # Get latest signal data
                    short_df = signals.get('short')
                    medium_df = signals.get('medium') 
                    
                    if short_df is None or short_df.empty or medium_df is None or medium_df.empty:
                        logger.warning(f"Insufficient signal data for {symbol}")
                        continue
                    
                    # Get latest signals
                    latest_short = short_df.iloc[-1]
                    latest_medium = medium_df.iloc[-1]
                    
                    buy_signal = latest_short['buy_signal'] and latest_medium['buy_signal']
                    sell_signal = latest_short['sell_signal'] and latest_medium['sell_signal']
                    
                    # Log signal analysis
                    logger.debug(f"{symbol} Signals - Buy: {buy_signal}, Sell: {sell_signal}, "
                               f"MACD: {latest_short['macd']:.4f}, Signal: {latest_short['macd_signal']:.4f}, "
                               f"Price: ${latest_short['close']:.2f}, EMA: ${latest_short['ema']:.2f}")
                    
                    # Calculate position size
                    current_price = latest_short['close']
                    position_size = self.risk_manager.calculate_position_size(
                        available_cash=balance,
                        price=current_price,
                        num_positions=len(PERP_MARKETS)
                    )
                    
                    logger.debug(f"Position sizing for {symbol}: {position_size:.8f} units")
                    
                    # Execute trading logic
                    executed_trade = False
                    
                    # BUY SIGNAL LOGIC
                    if buy_signal and not has_position:
                        if position_size > 0:
                            try:
                                # Calculate stop loss
                                stop_loss = latest_short['low'] - self.config['stop_buffer']
                                
                                logger.info(f"🔵 BUY SIGNAL for {symbol} - Price: ${current_price:.2f}, "
                                          f"Size: {position_size:.6f}, SL: ${stop_loss:.2f}")
                                
                                # Place buy order
                                tx_sig = await self.executor.place_market_order(
                                    symbol=symbol,
                                    side='BUY',
                                    quantity=position_size
                                )
                                
                                if tx_sig:
                                    # Record trade
                                    await self.portfolio_tracker.record_trade(
                                        symbol=symbol,
                                        side='BUY',
                                        price=current_price,
                                        quantity=position_size,
                                        sl=stop_loss,
                                        market_index=market_index,
                                        tx_signature=tx_sig
                                    )
                                    executed_trade = True
                                    logger.info(f"✅ Buy order executed for {symbol}")
                                
                            except Exception as e:
                                logger.error(f"Error executing buy order for {symbol}: {e}")
                    
                    # SELL SIGNAL LOGIC  
                    elif sell_signal and not has_position:
                        if position_size > 0:
                            try:
                                # Calculate stop loss
                                stop_loss = latest_short['high'] + self.config['stop_buffer']
                                
                                logger.info(f"🔴 SELL SIGNAL for {symbol} - Price: ${current_price:.2f}, "
                                          f"Size: {position_size:.6f}, SL: ${stop_loss:.2f}")
                                
                                # Place sell order
                                tx_sig = await self.executor.place_market_order(
                                    symbol=symbol,
                                    side='SELL',
                                    quantity=position_size
                                )
                                
                                if tx_sig:
                                    # Record trade
                                    await self.portfolio_tracker.record_trade(
                                        symbol=symbol,
                                        side='SELL', 
                                        price=current_price,
                                        quantity=position_size,
                                        sl=stop_loss,
                                        market_index=market_index,
                                        tx_signature=tx_sig
                                    )
                                    executed_trade = True
                                    logger.info(f"✅ Sell order executed for {symbol}")
                                
                            except Exception as e:
                                logger.error(f"Error executing sell order for {symbol}: {e}")
                    
                    # POSITION MANAGEMENT
                    elif has_position:
                        # Check for opposite signals to close position
                        position_side = current_position.get('side', 'unknown')
                        
                        should_close = False
                        if position_side == 'long' and sell_signal:
                            should_close = True
                            logger.info(f"🔄 Closing LONG position for {symbol} on sell signal")
                        elif position_side == 'short' and buy_signal:
                            should_close = True
                            logger.info(f"🔄 Closing SHORT position for {symbol} on buy signal")
                        
                        if should_close:
                            try:
                                close_tx = await self.executor.close_position(market_index)
                                if close_tx:
                                    logger.info(f"✅ Position closed for {symbol}")
                                    executed_trade = True
                            except Exception as e:
                                logger.error(f"Error closing position for {symbol}: {e}")
                    
                    # Track signal summary
                    signals_summary.append({
                        'symbol': symbol,
                        'buy_signal': buy_signal,
                        'sell_signal': sell_signal,
                        'has_position': has_position,
                        'executed_trade': executed_trade,
                        'price': current_price
                    })
                    
                except Exception as e:
                    logger.error(f"Error processing {symbol}: {e}")
                    continue
            
            # Log execution summary
            total_signals = sum(1 for s in signals_summary if s['buy_signal'] or s['sell_signal'])
            total_trades = sum(1 for s in signals_summary if s['executed_trade'])
            
            logger.debug(f"Strategy execution complete - Signals: {total_signals}, Trades: {total_trades}")
            
            if signals_summary:
                active_symbols = [s['symbol'] for s in signals_summary if s['buy_signal'] or s['sell_signal']]
                if active_symbols:
                    logger.info(f"Active signals: {', '.join(active_symbols)}")
                else:
                    logger.debug("No active signals in current analysis")
            
        except Exception as e:
            logger.error(f"Error in MACD strategy execution: {e}")
            raise
    
    async def generate_signals(self, symbol: str, timeframes: Dict[str, int]) -> Dict[str, pd.DataFrame]:
        """Generate MACD signals for multiple timeframes"""
        signals = {}
        
        for timeframe, periods in timeframes.items():
            try:
                # Get historical data
                df = await self.data_handler.get_historical_crypto_data(
                    ticker=symbol,
                    duration=periods, 
                    time_frame_unit='minutes'
                )
                
                if df.empty or len(df) < self.config['ema_filter']:
                    logger.warning(f"Insufficient data for {symbol} {timeframe}: {len(df)} bars")
                    continue
                
                # Calculate MACD indicators
                macd_indicator = ta.trend.MACD(
                    close=df['close'],
                    window_slow=self.config['slow_period'],
                    window_fast=self.config['fast_period'],
                    window_sign=self.config['signal_period']
                )
                
                df['macd'] = macd_indicator.macd()
                df['macd_signal'] = macd_indicator.macd_signal() 
                df['macd_histogram'] = macd_indicator.macd_diff()
                
                # EMA trend filter
                df['ema_filter'] = ta.trend.ema_indicator(
                    close=df['close'],
                    window=self.config['ema_filter']
                )
                
                # Generate crossover signals
                df['macd_bullish_cross'] = (
                    (df['macd'] > df['macd_signal']) & 
                    (df['macd'].shift(1) <= df['macd_signal'].shift(1))
                )
                
                df['macd_bearish_cross'] = (
                    (df['macd'] < df['macd_signal']) & 
                    (df['macd'].shift(1) >= df['macd_signal'].shift(1))
                )
                
                # Final buy/sell signals with EMA filter
                df['buy_signal'] = (
                    df['macd_bullish_cross'] & 
                    (df['close'] > df['ema_filter']) &
                    (abs(df['macd_histogram']) > self.config['min_signal_strength'])
                )
                
                df['sell_signal'] = (
                    df['macd_bearish_cross'] & 
                    (df['close'] < df['ema_filter']) &
                    (abs(df['macd_histogram']) > self.config['min_signal_strength'])
                )
                
                signals[timeframe] = df
                logger.debug(f"Generated signals for {symbol} {timeframe}: MACD={df['macd'].iloc[-1]:.4f}, Signal={df['macd_signal'].iloc[-1]:.4f}")
                
            except Exception as e:
                logger.error(f"Error generating signals for {symbol} {timeframe}: {e}")
                continue
        
        return signals
    
