"""
Enhanced 4H MACD Strategy for Drift Protocol with Advanced Hold Time Controls

This strategy implements:
- 4H MACD signals with EMA filter
- Smart hold time management (2H flexible vs 4H strict modes)
- Strong reversal override capability
- ATR-based risk management
- Emergency loss protection (3x ATR)
- Position sizing optimized for Drift minimums (90% allocation)

ChatGPT Integration: Implements flexible hold times and strong signal overrides
for enhanced market adaptability while maintaining strategy discipline.
"""

import asyncio
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple
import ta

from ..logger import logger
from ..config import (TIMEZONE, MACD_TARGET_SYMBOL, MACD_TIMEFRAME, MACD_FAST_PERIOD, 
                    MACD_SLOW_PERIOD, MACD_SIGNAL_PERIOD, EMA_FILTER_PERIOD, 
                    MACD_STOP_BUFFER, MIN_SIGNAL_STRENGTH, PERP_MARKETS,
                    get_market_index_by_symbol,
                    STRATEGY_NAME, DRIFT_ENV, BOT_VERSION, LEVERAGE_MULTIPLIER,
                    # === NEW 4H STRATEGY CONFIG IMPORTS ===
                    INITIAL_STOP_ATR_MULTIPLIER, TRAILING_STOP_ATR_MULTIPLIER, 
                    TRAILING_ACTIVATION_ATR, TAKE_PROFIT_ATR_MULTIPLIER, MAX_DRAWDOWN_PCT,
                    MAX_POSITION_PCT, POSITION_PCT, LEVERAGE_MULTIPLIER, MIN_POSITION_HOLD_TIME,
                    PRIMARY_TIMEFRAME, CONFIRM_TIMEFRAME, PRIMARY_PERIODS, CONFIRM_PERIODS,
                    SAFETY_MARGIN, CASH_ALLOCATION_MODE,
                    # === ADVANCED HOLD TIME CONTROLS ===
                    FLEXIBLE_HOLD_TIME, MIN_HOLD_TIME_FLEXIBLE, STRONG_REVERSAL_THRESHOLD, 
                    ENABLE_EARLY_REVERSAL_OVERRIDE)


class DriftMACDStrategy:
    async def cleanup_orphaned_orders(self):
        """Remove any orders that don't have corresponding positions"""
        try:
            orders_df = await self.broker.get_open_orders()
            positions_df = await self.broker.get_open_position()
            if not orders_df.empty:
                for _, order in orders_df.iterrows():
                    symbol = order['symbol']
                    market_index = order['market_index']
                    has_position = False
                    if not positions_df.empty:
                        has_position = (positions_df['market_index'] == market_index).any()
                    if not has_position:
                        logger.warning(f"🧹 Cleaning orphaned order for {symbol}")
                        await self.broker.close_order(symbol)
        except Exception as e:
            logger.error(f"Error cleaning orphaned orders: {e}")
    """
    Enhanced 4H MACD Strategy with ChatGPT Recommendations:
    
    Key Features:
    1. Flexible Hold Time Mode: 2H minimum vs 4H strict enforcement
    2. Strong Reversal Override: Early exits for exceptional opposite signals (MACD diff > 0.25)
    3. Emergency Loss Protection: 3x ATR automatic stops
    4. Smart Signal Management: Protects opposite signals during hold periods
    5. Position Sizing: 90% allocation to meet Drift 0.001 BTC minimums
    """
    
    def __init__(self, data_handler, broker, risk_manager, portfolio_tracker):
        # Core components
        self.data_handler = data_handler
        self.broker = broker
        self.risk_manager = risk_manager
        self.portfolio_tracker = portfolio_tracker
        
        # Strategy parameters
        self.target_symbol = MACD_TARGET_SYMBOL
        self.timeframe = MACD_TIMEFRAME
        
        # Handle timeframe conversion (support both int and string formats)
        if isinstance(self.timeframe, int):
            self.timeframe_minutes = self.timeframe  # Already in minutes
        elif isinstance(self.timeframe, str):
            if 'h' in self.timeframe:
                self.timeframe_minutes = int(self.timeframe.replace('h', '')) * 60
            else:
                self.timeframe_minutes = int(self.timeframe.replace('m', ''))
        else:
            self.timeframe_minutes = 240  # Default to 4H
            
        self.timezone = TIMEZONE
        
        # MACD parameters
        self.macd_fast = MACD_FAST_PERIOD
        self.macd_slow = MACD_SLOW_PERIOD
        self.macd_signal = MACD_SIGNAL_PERIOD
        self.ema_filter = EMA_FILTER_PERIOD
        self.position_pct = POSITION_PCT  # Use main position sizing config
        self.min_signal_strength = MIN_SIGNAL_STRENGTH
        
        # Advanced Risk Management Parameters (NEW)
        self.trailing_atr_multiplier = TRAILING_STOP_ATR_MULTIPLIER  # 3.0
        self.trailing_activation_atr = TRAILING_ACTIVATION_ATR       # 1.75
        self.take_profit_atr_multiplier = TAKE_PROFIT_ATR_MULTIPLIER # 5.5
        self.max_drawdown_pct = MAX_DRAWDOWN_PCT                     # 0.10
        self.initial_stop_atr_multiplier = INITIAL_STOP_ATR_MULTIPLIER # 2.5
        self.min_position_hold_time = MIN_POSITION_HOLD_TIME         # 240 minutes (4 hours)
        
        # Track starting equity for drawdown protection
        self.starting_equity = None
        self.trading_disabled = False
        
        # Position tracking for risk management
        self.position_entry_price = None
        self.position_entry_time = None
        self.position_side = None
        self.current_stop_loss = None
        self.current_take_profit = None
        
        # Get BTC-PERP market index
        self.market_index = next((m["market_index"] for m in PERP_MARKETS if m["symbol"] == self.target_symbol), 1)
        
        logger.info(f"🎯 MACD Strategy Enhanced - Advanced Hold Time & Reversal Controls")
        logger.info(f"📊 Symbol: {self.target_symbol} | Timeframe: {self.timeframe} | Position %: {self.position_pct}")
        logger.info(f"⚡ MACD: Fast({self.macd_fast}), Slow({self.macd_slow}), Signal({self.macd_signal})")
        
        # Hold Time Configuration
        if FLEXIBLE_HOLD_TIME:
            logger.info(f"🔄 FLEXIBLE HOLD MODE: {MIN_HOLD_TIME_FLEXIBLE}min minimum (2H) vs strict {self.min_position_hold_time}min (4H)")
        else:
            logger.info(f"🔒 STRICT HOLD MODE: {self.min_position_hold_time} minutes (4H strategy)")
        
        # Reversal Override Configuration  
        if ENABLE_EARLY_REVERSAL_OVERRIDE:
            logger.info(f"🎯 STRONG REVERSAL OVERRIDE: Enabled with {STRONG_REVERSAL_THRESHOLD} MACD threshold")
        else:
            logger.info(f"🚫 REVERSAL OVERRIDE: Disabled - strict hold time enforcement")
            
        logger.info(f"🛡️ Risk Management: Initial Stop: {INITIAL_STOP_ATR_MULTIPLIER}x ATR, Take Profit: {TAKE_PROFIT_ATR_MULTIPLIER}x ATR")
        logger.info(f"📈 Position Sizing: {POSITION_PCT}% of balance (90% for Drift minimums)")
        
        logger.debug(f"Full config details: {self.get_config()}")
    
    async def initialize(self):
        """Initialize strategy components (required by main.py)"""
        logger.info(f"🚀 Initializing {self.__class__.__name__} strategy...")
        # Clean up orphaned orders on startup
        await self.cleanup_orphaned_orders()
        # Initialize starting equity tracking
        try:
            balance = await self.broker.get_account_balance()
            if balance and balance > 0:
                self.starting_equity = balance
                logger.info(f"💰 Starting equity tracked: ${balance:.2f}")
            else:
                logger.warning("Could not retrieve balance for equity tracking")
        except Exception as e:
            logger.warning(f"Error initializing equity tracking: {e}")
        logger.info(f"✅ {self.__class__.__name__} strategy initialized successfully")
    
    async def run_strategy(self):
        """Main strategy execution method (required by main.py)"""
        await self.execute()
    
    def get_config(self) -> Dict:
        """Return strategy configuration"""
        return {
            'target_symbol': self.target_symbol,
            'timeframe_minutes': self.timeframe_minutes,
            'fast_period': self.macd_fast,
            'slow_period': self.macd_slow, 
            'signal_period': self.macd_signal,
            'ema_filter': self.ema_filter,
            'position_pct': self.position_pct,
            'min_signal_strength': self.min_signal_strength,
            'min_position_hold_time': self.min_position_hold_time,
            'trailing_atr_multiplier': self.trailing_atr_multiplier,
            'take_profit_atr_multiplier': self.take_profit_atr_multiplier,
            'max_drawdown_pct': self.max_drawdown_pct,
            'flexible_hold_time': FLEXIBLE_HOLD_TIME,
            'min_hold_time_flexible': MIN_HOLD_TIME_FLEXIBLE,
            'strong_reversal_threshold': STRONG_REVERSAL_THRESHOLD,
            'enable_early_reversal_override': ENABLE_EARLY_REVERSAL_OVERRIDE
        }
    
    async def execute(self):
        """Execute the enhanced MACD strategy with advanced hold time management"""
        logger.debug("=== Starting Enhanced MACD Strategy Execution ===")
        
        try:
            symbol = self.target_symbol
            
            # Get market data (ensure enough for MACD + EMA indicators)
            required_bars = max(self.macd_slow, self.ema_filter) + 10  # 178 bars needed
            bars_per_day = (24 * 60) // self.timeframe_minutes  # 6 for 4h
            duration_days = max(8, (required_bars // bars_per_day) + 2)  # ~32 days for 4h
            
            # Ensure 4-hour timeframe is used for MACD signals
            df = await self.data_handler.get_historical_crypto_data(symbol, duration_days, "4h")
            if df is None or len(df) < max(self.macd_slow, self.ema_filter) + 5:
                logger.warning(f"Insufficient data for {symbol}. Skipping execution.")
                return
            
            # Calculate ATR for risk management
            atr_indicator = ta.volatility.AverageTrueRange(
                high=df['high'], low=df['low'], close=df['close'], window=14
            )
            atr_value = atr_indicator.average_true_range().iloc[-1]
            current_price = df['close'].iloc[-1]
            
            # Generate signals
            signals = self.generate_macd_signals(df)
            if not signals:
                logger.debug("No valid MACD signals generated")
                return
            
            buy_signal = signals.get('buy_signal', False)
            sell_signal = signals.get('sell_signal', False)
            signal_strength = signals.get('signal_strength', 0)
            self._last_signal_strength = signal_strength  # Store for record_trade calls
            
            logger.info(f"📈 {symbol} @ ${current_price:.2f} | ATR: ${atr_value:.2f} | "
                       f"Buy: {buy_signal} | Sell: {sell_signal} | Strength: {signal_strength:.4f}")
            
            # Get account balance and position
            balance = await self.broker.get_account_balance()
            
            # Get position info using get_open_positions and filter for our symbol
            open_positions = await self.broker.get_open_positions()
            logger.debug(f"Open positions found: {len(open_positions)} positions")
            if open_positions:
                logger.debug(f"Position details: {open_positions}")
                
                # Separate PERP and SPOT positions for clarity
                perp_positions = [pos for pos in open_positions if pos.get('market_type') == 'perp']
                spot_positions = [pos for pos in open_positions if pos.get('market_type') == 'spot']
                logger.info(f"🔹 PERP positions: {len(perp_positions)} | SPOT positions: {len(spot_positions)}")
            
            # Get market index for symbol matching (BTC-PERP = market_index 1 = "MARKET_1")
            from ..config import get_market_index_by_symbol
            target_market_index = get_market_index_by_symbol(symbol)
            target_symbol_format = f"MARKET_{target_market_index}"
            
            current_position = None
            for pos in open_positions:
                logger.debug(f"Checking position: {pos}")
                # CRITICAL: Only match PERPETUAL positions, ignore SPOT positions
                if pos.get('market_type') == 'perp':
                    # Match by symbol formats for PERP markets only
                    if pos.get('symbol') == symbol or pos.get('symbol') == target_symbol_format or pos.get('market_index') == target_market_index:
                        current_position = pos
                        logger.info(f"📍 Found PERP position for {symbol} (format: {pos.get('symbol')}): {pos}")
                        break
                else:
                    logger.debug(f"🔄 Ignoring SPOT position: {pos.get('symbol')} (market_type: {pos.get('market_type')})")
            
            if not current_position:
                # No position found for this symbol
                current_position = {
                    'symbol': symbol,
                    'size': 0.0,
                    'qty': 0.0,  # Broker uses 'qty' field
                    'side': 'none',
                    'entry_price': 0.0,
                    'unrealized_pnl': 0.0,
                    'open': False
                }
            else:
                # Normalize position data - ensure 'size' field exists
                if 'qty' in current_position and 'size' not in current_position:
                    current_position['size'] = current_position['qty']
            
            # Check if we have any position (bot-managed or external)
            has_position = current_position and abs(current_position.get('size', 0)) > 0
            
            # DECISION SUMMARY - Clear indication of bot's action
            if buy_signal and not has_position:
                decision = "🚀 BUY SIGNAL - Ready to open LONG position"
            elif sell_signal and not has_position:
                decision = "🎯 SELL SIGNAL - Ready to open SHORT position"
            elif has_position and self.position_entry_price:
                decision = f"📊 MANAGING POSITION - Monitoring {self.position_side} position"
            elif has_position and not self.position_entry_price:
                decision = "🚫 EXTERNAL POSITION - Not bot-managed, waiting for clear"
            else:
                decision = "⏸️ HOLD - No qualifying signals or waiting for opportunity"
            
            logger.critical(f"📋 DECISION: {decision}")
            
            # SAFETY CHECK: Detect external positions vs bot-managed positions
            if has_position and not self.position_entry_price:
                # External position exists - bot will now take control and manage it
                self.position_entry_price = current_position.get('entry_price', 0)
                self.position_entry_time = datetime.now(TIMEZONE)
                self.position_side = "BUY" if current_position.get('qty', 0) > 0 else "SELL"
                self.current_stop_loss = None
                self.current_take_profit = None
                logger.info(f"🤖 Bot has adopted external position: {self.position_side} @ {self.position_entry_price}")
                # Now continue to normal management logic
            elif not has_position:
                # Account is clear - bot can now trade!
                logger.info(f"🎯 ACCOUNT CLEAR! Bot can execute trades based on signals")
            
            # Execute trading logic ONLY for bot-managed positions
            if buy_signal and not has_position:
                logger.critical(f"🚀 EXECUTING REAL BUY ORDER ON DRIFT!")
                tx_sig = await self.execute_buy_signal(symbol, current_price, balance, atr_value)
                # Wait for position to appear after order (polling, up to 10 seconds)
                found = False
                for _ in range(10):
                    open_positions = await self.broker.get_open_positions()
                    for pos in open_positions:
                        if pos.get('market_type') == 'perp' and (
                            pos.get('symbol') == symbol or
                            pos.get('symbol') == f"MARKET_{target_market_index}" or
                            pos.get('market_index') == target_market_index
                        ) and abs(pos.get('qty', 0)) > 0:
                            self.position_entry_price = pos.get('entry_price', 0)
                            self.position_entry_time = datetime.now(TIMEZONE)
                            self.position_side = "BUY" if pos.get('qty', 0) > 0 else "SELL"
                            found = True
                            logger.info(f"✅ Bot-managed position detected after BUY: {self.position_side} @ {self.position_entry_price}")
                            break
                    if found:
                        break
                    await asyncio.sleep(1)
                if not found:
                    # Try one last time after polling
                    open_positions = await self.broker.get_open_positions()
                    for pos in open_positions:
                        if pos.get('market_type') == 'perp' and (
                            pos.get('symbol') == symbol or
                            pos.get('symbol') == f"MARKET_{target_market_index}" or
                            pos.get('market_index') == target_market_index
                        ) and abs(pos.get('qty', 0)) > 0:
                            self.position_entry_price = pos.get('entry_price', 0)
                            self.position_entry_time = datetime.now(TIMEZONE)
                            self.position_side = "BUY" if pos.get('qty', 0) > 0 else "SELL"
                            logger.warning(f"⚠️ Bot-managed position detected after polling: {self.position_side} @ {self.position_entry_price}")
                            found = True
                            break
                if not found:
                    logger.warning("❌ No bot-managed position detected after BUY order. Will treat as external until next run.")
            elif sell_signal and not has_position:
                logger.critical(f"🚀 EXECUTING REAL SELL ORDER ON DRIFT!")
                tx_sig = await self.execute_sell_signal(symbol, current_price, balance, atr_value)
                # Wait for position to appear after order (polling, up to 10 seconds)
                found = False
                for _ in range(10):
                    open_positions = await self.broker.get_open_positions()
                    for pos in open_positions:
                        if pos.get('market_type') == 'perp' and (
                            pos.get('symbol') == symbol or
                            pos.get('symbol') == f"MARKET_{target_market_index}" or
                            pos.get('market_index') == target_market_index
                        ) and abs(pos.get('qty', 0)) > 0:
                            self.position_entry_price = pos.get('entry_price', 0)
                            self.position_entry_time = datetime.now(TIMEZONE)
                            self.position_side = "SELL" if pos.get('qty', 0) < 0 else "BUY"
                            found = True
                            logger.info(f"✅ Bot-managed position detected after SELL: {self.position_side} @ {self.position_entry_price}")
                            break
                    if found:
                        break
                    await asyncio.sleep(1)
                if not found:
                    # Try one last time after polling
                    open_positions = await self.broker.get_open_positions()
                    for pos in open_positions:
                        if pos.get('market_type') == 'perp' and (
                            pos.get('symbol') == symbol or
                            pos.get('symbol') == f"MARKET_{target_market_index}" or
                            pos.get('market_index') == target_market_index
                        ) and abs(pos.get('qty', 0)) > 0:
                            self.position_entry_price = pos.get('entry_price', 0)
                            self.position_entry_time = datetime.now(TIMEZONE)
                            self.position_side = "SELL" if pos.get('qty', 0) < 0 else "BUY"
                            logger.warning(f"⚠️ Bot-managed position detected after polling: {self.position_side} @ {self.position_entry_price}")
                            found = True
                            break
                if not found:
                    logger.warning("❌ No bot-managed position detected after SELL order. Will treat as external until next run.")
            elif buy_signal and has_position and self.position_entry_price:
                # Buy signal with bot-managed position - CHECK ADVANCED HOLD TIME FIRST
                if self.position_side == "SELL":
                    # Check if minimum hold time has passed before allowing reversal
                    if self.position_entry_time:
                        current_time = datetime.now(TIMEZONE)
                        hold_duration = (current_time - self.position_entry_time).total_seconds() / 60
                        
                        # Determine effective minimum hold time based on mode
                        effective_min_hold = MIN_HOLD_TIME_FLEXIBLE if FLEXIBLE_HOLD_TIME else self.min_position_hold_time
                        
                        if hold_duration < effective_min_hold:
                            remaining_time = effective_min_hold - hold_duration
                            logger.warning(f"🔄 OPPOSITE BUY SIGNAL DETECTED while holding SHORT")
                            logger.info(f"⏳ Hold time check: {hold_duration:.1f}min / {effective_min_hold}min ({'Flexible' if FLEXIBLE_HOLD_TIME else 'Strict'} mode)")
                            
                            # 🎯 STRONG REVERSAL OVERRIDE: Check for exceptionally strong opposite signals
                            if ENABLE_EARLY_REVERSAL_OVERRIDE and hold_duration >= 60:  # At least 1 hour
                                # Calculate current MACD for signal strength
                                df_current = await self.data_handler.get_historical_crypto_data(symbol, 3, "Hour")
                                if df_current is not None and len(df_current) > 0:
                                    macd_indicator = ta.trend.MACD(close=df_current['close'], 
                                                                 window_fast=self.macd_fast,
                                                                 window_slow=self.macd_slow, 
                                                                 window_sign=self.macd_signal)
                                    macd_diff = macd_indicator.macd_diff().iloc[-1]
                                    macd_diff_magnitude = abs(macd_diff) if not pd.isna(macd_diff) else 0
                                    
                                    if macd_diff_magnitude > STRONG_REVERSAL_THRESHOLD:
                                        logger.warning(f"🎯 STRONG REVERSAL OVERRIDE: MACD diff {macd_diff_magnitude:.4f} > {STRONG_REVERSAL_THRESHOLD}")
                                        logger.critical(f"🚀 Allowing early SHORT→LONG reversal due to exceptional signal strength!")
                                        await self.close_position_with_reason(symbol, "Strong Reversal Override - Early Exit")
                                        return
                            
                            logger.info(f"🚫 REVERSAL BLOCKED - {remaining_time:.1f}min remaining for hold requirement")
                            await self.manage_existing_position(symbol, current_position, current_price, atr_value)
                            return
                    
                    logger.critical(f"🔄 REVERSING POSITION: BUY signal while bot has SHORT (after hold period)")
                    await self.close_position_with_reason(symbol, "Opposite Signal - Buy while Short")
                else:  
                    logger.info(f"Buy signal with existing LONG - continue holding")
                    await self.manage_existing_position(symbol, current_position, current_price, atr_value)
            elif sell_signal and has_position and self.position_entry_price:
                # Sell signal with bot-managed position - CHECK ADVANCED HOLD TIME FIRST
                if self.position_side == "BUY":
                    # Check if minimum hold time has passed before allowing reversal
                    if self.position_entry_time:
                        current_time = datetime.now(TIMEZONE)
                        hold_duration = (current_time - self.position_entry_time).total_seconds() / 60
                        
                        # Determine effective minimum hold time based on mode
                        effective_min_hold = MIN_HOLD_TIME_FLEXIBLE if FLEXIBLE_HOLD_TIME else self.min_position_hold_time
                        
                        if hold_duration < effective_min_hold:
                            remaining_time = effective_min_hold - hold_duration
                            logger.warning(f"🔄 OPPOSITE SELL SIGNAL DETECTED while holding LONG")
                            logger.info(f"⏳ Hold time check: {hold_duration:.1f}min / {effective_min_hold}min ({'Flexible' if FLEXIBLE_HOLD_TIME else 'Strict'} mode)")
                            
                            # 🎯 STRONG REVERSAL OVERRIDE: Check for exceptionally strong opposite signals
                            if ENABLE_EARLY_REVERSAL_OVERRIDE and hold_duration >= 60:  # At least 1 hour
                                # Calculate current MACD for signal strength
                                df_current = await self.data_handler.get_historical_crypto_data(symbol, 3, "Hour")
                                if df_current is not None and len(df_current) > 0:
                                    macd_indicator = ta.trend.MACD(close=df_current['close'], 
                                                                 window_fast=self.macd_fast,
                                                                 window_slow=self.macd_slow, 
                                                                 window_sign=self.macd_signal)
                                    macd_diff = macd_indicator.macd_diff().iloc[-1]
                                    macd_diff_magnitude = abs(macd_diff) if not pd.isna(macd_diff) else 0
                                    
                                    if macd_diff_magnitude > STRONG_REVERSAL_THRESHOLD:
                                        logger.warning(f"🎯 STRONG REVERSAL OVERRIDE: MACD diff {macd_diff_magnitude:.4f} > {STRONG_REVERSAL_THRESHOLD}")
                                        logger.critical(f"🚀 Allowing early LONG→SHORT reversal due to exceptional signal strength!")
                                        await self.close_position_with_reason(symbol, "Strong Reversal Override - Early Exit")
                                        return
                            
                            logger.info(f"🚫 REVERSAL BLOCKED - {remaining_time:.1f}min remaining for hold requirement")
                            await self.manage_existing_position(symbol, current_position, current_price, atr_value)
                            return
                    
                    logger.critical(f"🔄 REVERSING POSITION: SELL signal while bot has LONG (after hold period)")
                    await self.close_position_with_reason(symbol, "Opposite Signal - Sell while Long")
                else:  
                    logger.info(f"Sell signal with existing SHORT - continue holding")
                    await self.manage_existing_position(symbol, current_position, current_price, atr_value)
            elif has_position and self.position_entry_price:
                # No signal but have bot-managed position - continue risk management
                logger.debug(f"Managing existing bot position: {self.position_side} @ ${self.position_entry_price:.2f}")
                await self.manage_existing_position(symbol, current_position, current_price, atr_value)
            
            logger.debug("=== MACD Strategy Execution Completed ===")
                
        except Exception as e:
            logger.error(f"Error in MACD strategy execution: {e}", exc_info=True)

    def generate_macd_signals(self, df: pd.DataFrame) -> Optional[Dict]:
        """Generate MACD signals with enhanced filtering"""
        try:
            if df is None or len(df) < max(self.macd_slow, self.ema_filter) + 5:
                return None
            
            # Calculate MACD
            macd_indicator = ta.trend.MACD(
                close=df['close'],
                window_fast=self.macd_fast,
                window_slow=self.macd_slow,
                window_sign=self.macd_signal
            )
            macd_line = macd_indicator.macd()
            macd_signal_line = macd_indicator.macd_signal()
            macd_histogram = macd_indicator.macd_diff()
            
            # Calculate EMA filter
            ema_filter = ta.trend.EMAIndicator(df['close'], window=self.ema_filter).ema_indicator()
            
            # Get current values
            current_price = df['close'].iloc[-1]
            current_macd = macd_line.iloc[-1]
            current_signal = macd_signal_line.iloc[-1]
            current_histogram = macd_histogram.iloc[-1]
            current_ema = ema_filter.iloc[-1]
            
            # Previous values for crossover detection
            prev_macd = macd_line.iloc[-2]
            prev_signal = macd_signal_line.iloc[-2]
            
            # Signal generation logic
            buy_signal = False
            sell_signal = False
            
            # MACD crossover logic
            macd_bullish_cross = current_macd > current_signal and prev_macd <= prev_signal
            macd_bearish_cross = current_macd < current_signal and prev_macd >= prev_signal
            
            # EMA trend filter
            price_above_ema = current_price > current_ema
            price_below_ema = current_price < current_ema
            
            # Log signal diagnostics so we can see WHY there's no signal
            logger.info(f"🔍 MACD: {current_macd:.2f} | Signal: {current_signal:.2f} | Hist: {current_histogram:.2f} | "
                       f"Prev MACD: {prev_macd:.2f} | Prev Signal: {prev_signal:.2f}")
            logger.info(f"🔍 EMA({self.ema_filter}): ${current_ema:.2f} | Price: ${current_price:.2f} | "
                       f"Price vs EMA: {'ABOVE ✅' if price_above_ema else 'BELOW ❌'} (gap: ${current_price - current_ema:.2f})")
            logger.info(f"🔍 Bullish cross: {macd_bullish_cross} | Bearish cross: {macd_bearish_cross} | "
                       f"Strength ({abs(current_histogram):.4f}) > {self.min_signal_strength}: {abs(current_histogram) > self.min_signal_strength}")
            
            # Generate signals with filters
            if macd_bullish_cross and price_above_ema and abs(current_histogram) > self.min_signal_strength:
                buy_signal = True
            elif macd_bearish_cross and price_below_ema and abs(current_histogram) > self.min_signal_strength:
                sell_signal = True
            
            return {
                'buy_signal': buy_signal,
                'sell_signal': sell_signal,
                'signal_strength': abs(current_histogram),
                'macd': current_macd,
                'macd_signal': current_signal,
                'macd_histogram': current_histogram,
                'ema_filter': current_ema,
                'price_vs_ema': 'above' if price_above_ema else 'below'
            }
            
        except Exception as e:
            logger.error(f"Error generating MACD signals: {e}")
            return None

    async def execute_buy_signal(self, symbol: str, price: float, balance: float, atr_value: float):
        """Execute buy signal with enhanced risk management"""
        try:
            if balance <= 0:
                logger.warning("Insufficient balance for buy order")
                return
            
            # Calculate position size with leverage (50% allocation × 2x leverage)
            position_value = balance * POSITION_PCT * LEVERAGE_MULTIPLIER
            quantity = position_value / price
            
            # Validate minimum order size for Drift (0.001 BTC)
            min_order_size = 0.001
            if quantity < min_order_size:
                logger.warning(f"Order size {quantity:.6f} BTC below Drift minimum {min_order_size} BTC")
                return
            
            logger.info(f"💰 Buy Signal: ${position_value:.2f} ({POSITION_PCT*100}% × {LEVERAGE_MULTIPLIER}x) = {quantity:.6f} BTC")
            
            # Calculate risk management levels
            initial_stop_loss = price - (self.initial_stop_atr_multiplier * atr_value)
            take_profit_level = price + (self.take_profit_atr_multiplier * atr_value)
            
            logger.info(f"🎯 Risk Management: Entry ${price:.2f} | Stop ${initial_stop_loss:.2f} | TP ${take_profit_level:.2f}")
            logger.info(f"📊 ATR: ${atr_value:.2f} | Stop Risk: {self.initial_stop_atr_multiplier}x | TP: {self.take_profit_atr_multiplier}x")
            
            # Execute the trade
            logger.info(f"📤 Executing BUY order: {quantity:.6f} {symbol} at market price")
            exec_result = await self.broker.place_market_order(
                symbol=symbol,
                quantity=quantity,
                side='BUY'
            )
            
            if exec_result:
                tx_sig = exec_result.get('tx_signature', '') if isinstance(exec_result, dict) else str(exec_result)
                execution_price = exec_result.get('execution_price', price) if isinstance(exec_result, dict) else price
                exec_qty = exec_result.get('execution_quantity', quantity) if isinstance(exec_result, dict) else quantity
                exec_fee = exec_result.get('fee', 0.0) if isinstance(exec_result, dict) else 0.0
                equity_after = exec_result.get('account_equity', 0.0) if isinstance(exec_result, dict) else 0.0
                latency_ms = exec_result.get('execution_latency_ms', 0.0) if isinstance(exec_result, dict) else 0.0
                    
                logger.info(f"✅ BUY order executed: {tx_sig}")
                logger.info(f"📊 EXECUTION: {exec_qty:.6f} @ ${execution_price:.2f} | Fee: ${exec_fee:.4f} | Latency: {latency_ms:.0f}ms")
                
                # Set position tracking with enhanced parameters
                self.position_entry_price = execution_price
                self.position_entry_time = datetime.now(TIMEZONE)
                self.position_side = "BUY"
                self.current_stop_loss = initial_stop_loss
                self.current_take_profit = take_profit_level
                
                # Record trade with full execution metadata
                self.portfolio_tracker.record_trade(
                    symbol=symbol,
                    side="BUY",
                    price=execution_price,
                    quantity=exec_qty,
                    sl=initial_stop_loss,
                    tp=take_profit_level,
                    tx_signature=tx_sig,
                    market_index=self.market_index,
                    fee=exec_fee,
                    account_equity=equity_after,
                    oracle_price_at_entry=price,
                    strategy_id=STRATEGY_NAME,
                    signal_type='macd_momentum',
                    signal_confidence=getattr(self, '_last_signal_strength', 0),
                    order_type='market',
                    env=DRIFT_ENV,
                    leverage=LEVERAGE_MULTIPLIER,
                    execution_latency_ms=latency_ms,
                    bot_version=BOT_VERSION,
                )
                
        except Exception as e:
            logger.error(f"Error executing buy signal: {e}")

    async def execute_sell_signal(self, symbol: str, price: float, balance: float, atr_value: float):
        """Execute sell signal with enhanced risk management"""
        try:
            if balance <= 0:
                logger.warning("Insufficient balance for sell order")
                return
            
            # Calculate position size with leverage (50% allocation × 2x leverage)
            position_value = balance * POSITION_PCT * LEVERAGE_MULTIPLIER
            quantity = position_value / price
            
            # Validate minimum order size for Drift (0.001 BTC)
            min_order_size = 0.001
            if quantity < min_order_size:
                logger.warning(f"Order size {quantity:.6f} BTC below Drift minimum {min_order_size} BTC")
                return
            
            logger.info(f"💰 Sell Signal: ${position_value:.2f} ({POSITION_PCT*100}% × {LEVERAGE_MULTIPLIER}x) = {quantity:.6f} BTC")
            
            # Calculate risk management levels
            initial_stop_loss = price + (self.initial_stop_atr_multiplier * atr_value)
            take_profit_level = price - (self.take_profit_atr_multiplier * atr_value)
            
            logger.info(f"🎯 Risk Management: Entry ${price:.2f} | Stop ${initial_stop_loss:.2f} | TP ${take_profit_level:.2f}")
            logger.info(f"📊 ATR: ${atr_value:.2f} | Stop Risk: {self.initial_stop_atr_multiplier}x | TP: {self.take_profit_atr_multiplier}x")
            
            # Execute the trade
            logger.info(f"📤 Executing SELL order: {quantity:.6f} {symbol} at market price")
            exec_result = await self.broker.place_market_order(
                symbol=symbol,
                quantity=quantity,
                side='SELL'
            )
            
            if exec_result:
                tx_sig = exec_result.get('tx_signature', '') if isinstance(exec_result, dict) else str(exec_result)
                execution_price = exec_result.get('execution_price', price) if isinstance(exec_result, dict) else price
                exec_qty = exec_result.get('execution_quantity', quantity) if isinstance(exec_result, dict) else quantity
                exec_fee = exec_result.get('fee', 0.0) if isinstance(exec_result, dict) else 0.0
                equity_after = exec_result.get('account_equity', 0.0) if isinstance(exec_result, dict) else 0.0
                latency_ms = exec_result.get('execution_latency_ms', 0.0) if isinstance(exec_result, dict) else 0.0
                
                logger.info(f"✅ SELL order executed: {tx_sig}")
                logger.info(f"📊 EXECUTION: {exec_qty:.6f} @ ${execution_price:.2f} | Fee: ${exec_fee:.4f} | Latency: {latency_ms:.0f}ms")
                
                # Set position tracking with enhanced parameters
                self.position_entry_price = execution_price
                self.position_entry_time = datetime.now(TIMEZONE)
                self.position_side = "SELL"
                self.current_stop_loss = initial_stop_loss
                self.current_take_profit = take_profit_level
                
                # Record trade with full execution metadata
                self.portfolio_tracker.record_trade(
                    symbol=symbol,
                    side="SELL",
                    price=execution_price,
                    quantity=exec_qty,
                    sl=initial_stop_loss,
                    tp=take_profit_level,
                    tx_signature=tx_sig,
                    market_index=self.market_index,
                    fee=exec_fee,
                    account_equity=equity_after,
                    oracle_price_at_entry=price,
                    strategy_id=STRATEGY_NAME,
                    signal_type='macd_momentum',
                    signal_confidence=getattr(self, '_last_signal_strength', 0),
                    order_type='market',
                    env=DRIFT_ENV,
                    leverage=LEVERAGE_MULTIPLIER,
                    execution_latency_ms=latency_ms,
                    bot_version=BOT_VERSION,
                )
                
        except Exception as e:
            logger.error(f"Error executing sell signal: {e}")

    async def manage_existing_position(self, symbol: str, position, current_price: float, atr_value: float):
        """Enhanced position management with flexible hold time controls"""
        try:
            # CRITICAL: Only manage positions that actually exist on Drift Protocol
            if not position or abs(position.get('qty', 0)) == 0:
                logger.debug(f"🚫 No actual position found on Drift Protocol for {symbol}")
                # Clear any stale bot tracking
                self.position_entry_price = None
                self.position_side = None
                self.position_entry_time = None
                return
            
            # Verify bot tracking matches actual position
            actual_position_size = position.get('qty', 0)
            actual_position_side = 'BUY' if actual_position_size > 0 else 'SELL' if actual_position_size < 0 else None
            
            if not self.position_entry_price or not self.position_side:
                logger.warning(f"� Found Drift position but no bot tracking - Position may be external")
                logger.warning(f"📊 Drift Position: {actual_position_side} {abs(actual_position_size):.6f} {symbol}")
                logger.info(f"🤖 Bot only manages positions it opens itself")
                return
            
            # Verify bot tracking matches Drift reality
            if self.position_side != actual_position_side:
                logger.error(f"❌ TRACKING MISMATCH! Bot thinks: {self.position_side}, Drift shows: {actual_position_side}")
                logger.error(f"🔧 Clearing incorrect bot tracking...")
                self.position_entry_price = None
                self.position_side = None
                self.position_entry_time = None
                return
            
            # 🔒 SMART FLEXIBLE HOLD TIME CHECK
            if self.position_entry_time:
                current_time = datetime.now(TIMEZONE)
                hold_duration = (current_time - self.position_entry_time).total_seconds() / 60  # minutes
                
                # Determine effective minimum hold time based on mode
                effective_min_hold = MIN_HOLD_TIME_FLEXIBLE if FLEXIBLE_HOLD_TIME else self.min_position_hold_time
                
                if hold_duration < effective_min_hold:
                    remaining_time = effective_min_hold - hold_duration
                    
                    # Calculate current profit/loss for decision making (always use total_profit)
                    entry_price = self.position_entry_price
                    side = self.position_side
                    actual_qty = position.get('qty', 0)
                    if side == "BUY":
                        profit_per_unit = current_price - entry_price
                    else:  # SELL
                        profit_per_unit = entry_price - current_price
                    total_profit = profit_per_unit * abs(actual_qty)
                    profit_pct = (profit_per_unit / entry_price) * 100
                    # Emergency loss threshold based on actual position
                    emergency_loss_threshold = 3.0 * atr_value * abs(actual_qty)
                    if total_profit < -emergency_loss_threshold:
                        logger.warning(f"🚨 EMERGENCY LOSS THRESHOLD BREACHED!")
                        logger.warning(f"💸 Loss: ${total_profit:.2f} exceeds emergency threshold: ${-emergency_loss_threshold:.2f}")
                        logger.warning(f"⚡ ALLOWING EMERGENCY EXIT despite minimum hold time")
                        # Continue to normal exit logic (don't return)
                    else:
                        # BLOCK only take profit and normal exits during hold period
                        hold_mode = "Flexible (2H)" if FLEXIBLE_HOLD_TIME else "Strict (4H)"
                        logger.info(f"⏳ HOLD TIME CHECK: {hold_duration:.1f}min / {effective_min_hold}min "
                                  f"(⏰ {remaining_time:.1f}min remaining) [{hold_mode}]")
                        logger.info(f"💰 Position: {self.position_side} {abs(actual_qty):.6f} {symbol} @ ${entry_price:.2f}")
                        logger.info(f"📊 Current: ${current_price:.2f} | Total P&L: ${total_profit:.2f} ({profit_pct:+.2f}%)")
                        logger.info(f"🛡️ Emergency stop available if loss > ${emergency_loss_threshold:.2f}")
                        logger.info(f"🚫 Normal exits blocked until hold complete")
                        return  # 🚫 Exit early - prevent normal exits during minimum hold period
            
            # Calculate current profit/loss based on ACTUAL position data (always use total_profit)
            entry_price = self.position_entry_price
            side = self.position_side
            actual_qty = position.get('qty', 0)
            if side == "BUY":
                profit_per_unit = current_price - entry_price
            else:  # SELL
                profit_per_unit = entry_price - current_price
            total_profit = profit_per_unit * abs(actual_qty)
            profit_pct = (profit_per_unit / entry_price) * 100
            logger.info(f"📊 Position Management: {side} {abs(actual_qty):.6f} {symbol} @ ${entry_price:.2f}")
            logger.info(f"📈 Current: ${current_price:.2f} | Total P&L: ${total_profit:.2f} ({profit_pct:+.2f}%)")

            # 📸 Record position snapshot for unrealized PnL tracking
            try:
                equity = await self.broker.get_account_balance()
                self.portfolio_tracker.record_position_snapshot(
                    symbol=symbol,
                    mark_price=current_price,
                    position_size=abs(actual_qty),
                    side=side,
                    entry_price=entry_price,
                    unrealized_pnl=total_profit,
                    account_equity=equity,
                )
            except Exception as snap_err:
                logger.debug(f"Snapshot write skipped: {snap_err}")

            # 🎯 TAKE PROFIT CHECK (Priority 1)
            take_profit_triggered = False
            # Ensure take profit is set
            if self.current_take_profit is None:
                if side == "BUY":
                    self.current_take_profit = entry_price + (self.take_profit_atr_multiplier * atr_value)
                else:
                    self.current_take_profit = entry_price - (self.take_profit_atr_multiplier * atr_value)
                logger.warning(f"Take profit was None, initialized to ${self.current_take_profit:.2f}")
            if side == "BUY" and current_price >= self.current_take_profit:
                take_profit_triggered = True
                logger.info(f"🎯 TAKE PROFIT TRIGGERED! Target: ${self.current_take_profit:.2f}, Current: ${current_price:.2f}")
            elif side == "SELL" and current_price <= self.current_take_profit:
                take_profit_triggered = True
                logger.info(f"🎯 TAKE PROFIT TRIGGERED! Target: ${self.current_take_profit:.2f}, Current: ${current_price:.2f}")
            if take_profit_triggered:
                logger.critical(f"🎯 EXECUTING TAKE PROFIT TRADE ON DRIFT PLATFORM!")
                await self.close_position_with_reason(symbol, "Take Profit Reached")
                return
            # 📈 TRAILING STOP LOGIC (Priority 2)
            activation_threshold = self.trailing_activation_atr * atr_value
            if total_profit > activation_threshold:  # Only trail when total profit exceeds threshold
                if side == "BUY":
                    # Trail stop up for long positions
                    new_stop = current_price - (self.trailing_atr_multiplier * atr_value)
                    if self.current_stop_loss is None or new_stop > self.current_stop_loss:
                        self.current_stop_loss = new_stop
                        logger.info(f"📈 TRAILING STOP UPDATED: ${new_stop:.2f} (trailing by {self.trailing_atr_multiplier}x ATR)")
                else:  # SELL
                    # Trail stop down for short positions
                    new_stop = current_price + (self.trailing_atr_multiplier * atr_value)
                    if self.current_stop_loss is None or new_stop < self.current_stop_loss:
                        self.current_stop_loss = new_stop
                        logger.info(f"📉 TRAILING STOP UPDATED: ${new_stop:.2f} (trailing by {self.trailing_atr_multiplier}x ATR)")
            
            # 🛑 STOP LOSS CHECK (Priority 3)
            stop_loss_triggered = False
            # Ensure stop loss is set
            if self.current_stop_loss is None:
                if side == "BUY":
                    self.current_stop_loss = entry_price - (self.initial_stop_atr_multiplier * atr_value)
                else:
                    self.current_stop_loss = entry_price + (self.initial_stop_atr_multiplier * atr_value)
                logger.warning(f"Stop loss was None, initialized to ${self.current_stop_loss:.2f}")
            if side == "BUY" and current_price <= self.current_stop_loss:
                stop_loss_triggered = True
                logger.warning(f"🛑 STOP LOSS TRIGGERED! Stop: ${self.current_stop_loss:.2f}, Current: ${current_price:.2f}")
            elif side == "SELL" and current_price >= self.current_stop_loss:
                stop_loss_triggered = True
                logger.warning(f"🛑 STOP LOSS TRIGGERED! Stop: ${self.current_stop_loss:.2f}, Current: ${current_price:.2f}")
            
            if stop_loss_triggered:
                logger.critical(f"🛑 EXECUTING STOP LOSS TRADE ON DRIFT PLATFORM!")
                await self.close_position_with_reason(symbol, "Stop Loss Hit")
                return
                
        except Exception as e:
            logger.error(f"Error managing position: {e}")

    async def close_position_with_reason(self, symbol: str, reason: str):
        """Close position with specified reason"""
        try:
            if not self.position_entry_price or not self.position_side:
                logger.warning("No bot position to close")
                return
            
            # Get current market price BEFORE closing (this is the actual close price)
            try:
                data_handler = self.data_handler if hasattr(self, 'data_handler') else None
                if data_handler:
                    df = await data_handler.get_historical_data(symbol, periods=1, timeframe_minutes=1)
                    if not df.empty:
                        current_market_price = float(df['close'].iloc[-1])
                    else:
                        current_market_price = None
                else:
                    current_market_price = None
            except Exception as e:
                logger.warning(f"Could not get current market price: {e}")
                current_market_price = None
                
            # Get current position from broker
            open_positions = await self.broker.get_open_positions()
            position = None
            
            # Get market index for symbol matching and filter PERP positions only
            from ..config import get_market_index_by_symbol
            target_market_index = get_market_index_by_symbol(symbol)
            target_symbol_format = f"MARKET_{target_market_index}"
            
            for pos in open_positions:
                # CRITICAL: Only match PERPETUAL positions for closing
                if pos.get('market_type') == 'perp':
                    if pos.get('symbol') == symbol or pos.get('symbol') == target_symbol_format or pos.get('market_index') == target_market_index:
                        position = pos
                        logger.info(f"📍 Found PERP position to close: {pos}")
                        break
            
            if not position or abs(position.get('qty', 0)) == 0:
                logger.warning("No active PERP position found to close")
                return
            
            # Determine close side (opposite of entry)
            close_side = 'SELL' if self.position_side == 'BUY' else 'BUY'
            quantity = abs(position.get('qty', 0))
            min_order_size = 0.001
            if quantity < min_order_size:
                logger.warning(f"❌ Close order size {quantity:.6f} BTC below Drift minimum {min_order_size} BTC. Position not closed.")
                return
            logger.critical(f"🚪 CLOSING POSITION: {reason}")
            logger.info(f"📤 Close order: {close_side} {quantity} {symbol}")
            # Execute close order
            exec_result = await self.broker.place_market_order(
                symbol=symbol,
                quantity=quantity,
                side=close_side
            )
            
            if exec_result:
                tx_sig = exec_result.get('tx_signature', '') if isinstance(exec_result, dict) else str(exec_result)
                exec_price_from_broker = exec_result.get('execution_price', 0.0) if isinstance(exec_result, dict) else 0.0

                # Use broker execution price if available, then current market price, then fallback
                if exec_price_from_broker and exec_price_from_broker > 0:
                    execution_price = exec_price_from_broker
                    logger.info(f"💰 Using broker execution price: ${execution_price:.2f}")
                elif current_market_price:
                    execution_price = current_market_price
                    logger.info(f"💰 Using market price as close price: ${execution_price:.2f}")
                else:
                    execution_details = await self.broker.get_execution_details(symbol, tx_sig)
                    execution_price = execution_details.get('execution_price') if execution_details else self.position_entry_price
                    logger.warning(f"⚠️ Using fallback close price: ${execution_price:.2f}")
                
                # Calculate actual realized P&L with Drift fees and funding
                from ..portfolio.portfolio_tracker import DriftPnLCalculator
                
                entry_price = self.position_entry_price
                hold_duration_minutes = (datetime.now(TIMEZONE) - self.position_entry_time).total_seconds() / 60
                hold_duration_hours = hold_duration_minutes / 60
                
                # Get P&L breakdown including fees and funding
                pnl_breakdown = DriftPnLCalculator.calculate_realized_pnl(
                    entry_price=entry_price,
                    close_price=execution_price,
                    quantity=quantity,
                    side=self.position_side,
                    hold_hours=hold_duration_hours,
                    funding_rate=0.0,  # TODO: Fetch actual funding rate from Drift API
                    is_maker=False  # Market orders are taker orders
                )
                
                gross_pnl = pnl_breakdown['gross_pnl']
                net_pnl = pnl_breakdown['net_pnl']
                entry_fee = pnl_breakdown['entry_fee']
                close_fee = pnl_breakdown['close_fee']
                funding_paid = pnl_breakdown['funding_paid']
                total_costs = pnl_breakdown['total_costs']
                
                logger.info(DriftPnLCalculator.format_pnl_report(pnl_breakdown))
                logger.info(f"💰 Realized P&L Breakdown:")
                logger.info(f"  Entry: ${entry_price:.2f} → Close: ${execution_price:.2f} | Hold: {hold_duration_minutes:.1f}min")
                logger.info(f"  Gross P&L: ${gross_pnl:.2f}")
                logger.info(f"  Fees (Entry+Close): ${entry_fee + close_fee:.2f}")
                logger.info(f"  Funding Paid: ${funding_paid:.2f}")
                logger.info(f"  ━━━ NET P&L: ${net_pnl:.2f} ({pnl_breakdown['net_pnl_pct']:+.2f}%)")
                
                # Get equity & oracle at close time
                close_equity = await self.broker.get_account_balance()
                close_oracle = execution_price  # oracle already used to determine exec price

                # Record the CLOSE trade with complete P&L breakdown
                self.portfolio_tracker.record_trade(
                    symbol=symbol,
                    side="CLOSE",
                    price=execution_price,  # Actual close price
                    quantity=quantity,  # Actual quantity closed
                    sl=0.0,
                    tp=0.0,
                    tx_signature=tx_sig,
                    market_index=self.market_index,
                    pnl=gross_pnl,  # ✅ Gross realized P&L
                    status="CLOSED",
                    # Drift-specific data
                    fee=entry_fee + close_fee,  # Total fees
                    order_type="market",
                    duration_seconds=hold_duration_minutes * 60,
                    entry_hold_minutes=hold_duration_minutes,
                    funding_paid=funding_paid,
                    cumulative_funding=funding_paid,
                    taker_fee_rate=DriftPnLCalculator.DEFAULT_TAKER_FEE,
                    net_pnl_after_fees=net_pnl,
                    account_equity=close_equity,
                    oracle_price_at_entry=close_oracle,
                    strategy_id=STRATEGY_NAME,
                    env=DRIFT_ENV,
                    leverage=LEVERAGE_MULTIPLIER,
                    bot_version=BOT_VERSION,
                )
                
                logger.info(f"💰 CLOSE trade recorded: {close_side} {quantity} @ ${execution_price:.2f}, P&L: ${net_pnl:.2f}")
                
                # Reset position tracking
                self.position_entry_price = None
                self.position_entry_time = None
                self.position_side = None
                self.current_stop_loss = None
                self.current_take_profit = None
                
                logger.info(f"✅ Position closed successfully: {tx_sig}")
                logger.info(f"📝 Reason: {reason}")
            
        except Exception as e:
            logger.error(f"Error closing position: {e}")
    
    async def close_all_positions(self):
        """
        Close all open PERP positions for this strategy's symbol
        Called during shutdown or end of trading session
        """
        try:
            logger.info("🚪 Attempting to close all positions...")
            
            # Get all open positions
            open_positions = await self.broker.get_open_positions()
            if not open_positions:
                logger.info("✅ No positions to close")
                return
            
            # Find any PERP position for our target symbol
            target_market_index = get_market_index_by_symbol(MACD_TARGET_SYMBOL)
            
            for pos in open_positions:
                if pos.get('market_type') == 'perp' and pos.get('market_index') == target_market_index:
                    qty = pos.get('qty', 0)
                    if abs(qty) > 0:
                        # Determine close side (opposite of position direction)
                        close_side = 'SELL' if qty > 0 else 'BUY'
                        
                        logger.info(f"🚪 Closing {MACD_TARGET_SYMBOL} position: {close_side} {abs(qty)}")
                        
                        exec_result = await self.broker.place_market_order(
                            symbol=MACD_TARGET_SYMBOL,
                            quantity=abs(qty),
                            side=close_side
                        )
                        
                        if exec_result:
                            tx_sig = exec_result.get('tx_signature', '') if isinstance(exec_result, dict) else str(exec_result)
                            execution_price = exec_result.get('execution_price', 0.0) if isinstance(exec_result, dict) else 0.0
                            exec_fee = exec_result.get('fee', 0.0) if isinstance(exec_result, dict) else 0.0
                            equity_after = exec_result.get('account_equity', 0.0) if isinstance(exec_result, dict) else 0.0

                            # Fallback: get price from execution details if not in result
                            if execution_price == 0.0:
                                det = await self.broker.get_execution_details(MACD_TARGET_SYMBOL, tx_sig)
                                execution_price = det.get('execution_price', 0.0) if det else 0.0

                            # Calculate PnL if we have entry tracking
                            gross_pnl = 0.0
                            net_pnl = 0.0
                            hold_minutes = 0.0
                            funding_paid = 0.0
                            entry_fee = 0.0
                            close_fee = exec_fee

                            if self.position_entry_price and self.position_entry_price > 0 and execution_price > 0:
                                from ..portfolio.portfolio_tracker import DriftPnLCalculator
                                hold_minutes = (datetime.now(TIMEZONE) - self.position_entry_time).total_seconds() / 60 if self.position_entry_time else 0
                                pnl_breakdown = DriftPnLCalculator.calculate_realized_pnl(
                                    entry_price=self.position_entry_price,
                                    close_price=execution_price,
                                    quantity=abs(qty),
                                    side=self.position_side or ('BUY' if qty > 0 else 'SELL'),
                                    hold_hours=hold_minutes / 60,
                                    funding_rate=0.0,
                                    is_maker=False
                                )
                                gross_pnl = pnl_breakdown['gross_pnl']
                                net_pnl = pnl_breakdown['net_pnl']
                                entry_fee = pnl_breakdown['entry_fee']
                                close_fee = pnl_breakdown['close_fee']
                                funding_paid = pnl_breakdown['funding_paid']
                                logger.info(f"💰 Shutdown close PnL: gross=${gross_pnl:.2f}, net=${net_pnl:.2f}")

                            self.portfolio_tracker.record_trade(
                                symbol=MACD_TARGET_SYMBOL,
                                side="CLOSE",
                                price=execution_price,
                                quantity=abs(qty),
                                sl=0.0,
                                tp=0.0,
                                tx_signature=tx_sig,
                                market_index=target_market_index,
                                pnl=gross_pnl,
                                status="CLOSED",
                                fee=entry_fee + close_fee,
                                order_type="market",
                                duration_seconds=hold_minutes * 60,
                                entry_hold_minutes=hold_minutes,
                                funding_paid=funding_paid,
                                cumulative_funding=funding_paid,
                                net_pnl_after_fees=net_pnl,
                                account_equity=equity_after,
                                oracle_price_at_entry=execution_price,
                                strategy_id=STRATEGY_NAME,
                                env=DRIFT_ENV,
                                leverage=LEVERAGE_MULTIPLIER,
                                bot_version=BOT_VERSION,
                            )
                            
                            logger.info(f"✅ Position closed on shutdown: {tx_sig}")
                            
                            # Clear tracking
                            self.position_entry_price = None
                            self.position_side = None
                            self.position_entry_time = None
            
            logger.info("✅ All positions closed successfully")
            
        except Exception as e:
            logger.error(f"Error closing all positions: {e}")
    
    async def cleanup(self):
        """Cleanup resources before shutdown"""
        try:
            logger.info("🧹 Cleaning up strategy resources...")
            
            # Close Drift client connection
            if self.broker and hasattr(self.broker, 'drift_client'):
                if self.broker.drift_client:
                    await self.broker.drift_client.unsubscribe()
                    logger.info("✅ Drift client unsubscribed")
            
            logger.info("✅ Cleanup completed")
            
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")