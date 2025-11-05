

"""
Portfolio tracking and trade recording for Drift Protocol
"""
import pandas as pd
import pendulum as dt
from datetime import datetime
from typing import Optional, Dict, Any
from ..config import TRADES_FILE, TIMEZONE
from ..logger import logger


class DriftPortfolioTracker:
    def __init__(self):
        """Initialize the Drift portfolio tracker"""
        self.expected_cols = [
            # Core identification
            'timestamp', 'symbol', 'market_index', 'market_type',
            # Order details
            'side', 'order_type', 'price', 'quantity', 'fee', 'slippage_bps',
            # Risk management
            'sl', 'tp',
            # Trade outcome
            'pnl', 'unrealized_pnl', 'status', 'duration_seconds',
            # Account context
            'account_equity', 'leverage', 'sub_account_id',
            # Strategy metadata
            'strategy_id', 'signal_confidence', 'signal_type',
            # Blockchain data
            'tx_signature', 'slot', 'block_time',
            # Execution quality
            'oracle_price_at_entry', 'execution_latency_ms', 'bot_version', 'env',
            # Drift-specific costs
            'funding_paid', 'cumulative_funding', 'entry_hold_minutes',
            'taker_fee_rate', 'maker_fee_rate', 'net_pnl_after_fees'
        ]
        self.trades_info = self._load_trades()
        self.session_trades = []  # Track trades for current session
        self.position_funding_tracker = {}  # Track cumulative funding for open positions
    
    def _load_trades(self):
        """Load trades from CSV or create new dataframe"""
        try:
            trades_info = pd.read_csv(TRADES_FILE)
            trades_info = trades_info.loc[:, ~trades_info.columns.str.contains("^Unnamed")]
            
            # Ensure missing columns are added
            for col in self.expected_cols:
                if col not in trades_info.columns:
                    trades_info[col] = None
            
            trades_info = trades_info[self.expected_cols]
            
            # Convert timestamp column to datetime if it exists
            if 'timestamp' in trades_info.columns:
                trades_info['timestamp'] = pd.to_datetime(trades_info['timestamp'], format='mixed', utc=True)
                trades_info = trades_info.set_index('timestamp')
            else:
                trades_info.index.name = "timestamp"
                
        except FileNotFoundError:
            trades_info = pd.DataFrame(columns=self.expected_cols)
            trades_info.index.name = "timestamp"
            
        return trades_info
    
    def record_trade(self, symbol: str, side: str, price: float, quantity: float, 
                     sl: float = 0, tp: float = 0, tx_signature: str = "", 
                     market_index: Optional[int] = None, market_type: str = "perp",
                     # New parameters for enhanced logging
                     order_type: str = "market", fee: float = 0.0, slippage_bps: float = 0.0,
                     pnl: float = 0.0, unrealized_pnl: float = 0.0, status: str = "OPEN",
                     duration_seconds: float = 0.0, account_equity: float = 0.0,
                     leverage: float = 1.0, sub_account_id: int = 0,
                     strategy_id: str = "unknown", signal_confidence: float = 0.0,
                     signal_type: str = "unknown", slot: int = 0, block_time: str = "",
                     oracle_price_at_entry: float = 0.0, execution_latency_ms: float = 0.0,
                     bot_version: str = "1.0", env: str = "devnet",
                     # Drift-specific parameters
                     funding_paid: float = 0.0, cumulative_funding: float = 0.0,
                     entry_hold_minutes: float = 0.0, taker_fee_rate: float = 0.0005,
                     maker_fee_rate: float = 0.0002, net_pnl_after_fees: float = 0.0):
        """
        Record a trade to the portfolio with comprehensive metadata
        
        Args:
            # Core order info
            symbol: Market symbol (e.g., "SOL-PERP")
            side: 'BUY', 'SELL', or 'CLOSE'
            price: Trade price
            quantity: Trade quantity
            sl: Stop loss price
            tp: Take profit price
            tx_signature: Solana transaction signature
            market_index: Drift market index
            market_type: 'perp' or 'spot'
            
            # Order quality
            order_type: 'market', 'limit', 'reduceOnly', etc.
            fee: Fee paid in quote currency
            slippage_bps: Slippage in basis points
            
            # Trade outcome
            pnl: Realized profit/loss
            unrealized_pnl: Floating PnL if still open
            status: 'OPEN', 'CLOSED', 'CANCELLED'
            duration_seconds: How long the trade lasted
            
            # Account context
            account_equity: Total account equity after trade
            leverage: Position leverage at entry
            sub_account_id: Drift sub-account
            
            # Strategy metadata
            strategy_id: Which strategy triggered it
            signal_confidence: Strength of signal (0-1)
            signal_type: 'momentum', 'mean_reversion', etc.
            
            # Blockchain data
            slot: Solana slot number
            block_time: On-chain timestamp
            
            # Execution quality
            oracle_price_at_entry: Oracle price for slippage calc
            execution_latency_ms: Signal → fill latency
            bot_version: Algorithm version
            env: 'mainnet-beta' or 'devnet'
            
            # Drift-specific costs
            funding_paid: Funding fee paid during this trade session (in quote)
            cumulative_funding: Total funding paid since position open
            entry_hold_minutes: How long position was held
            taker_fee_rate: Drift taker fee percentage (default 0.05%)
            maker_fee_rate: Drift maker fee percentage (default 0.02%)
            net_pnl_after_fees: PnL minus all fees and funding
        """
        timestamp = datetime.now(TIMEZONE)
        
        # ============================================================
        # VALIDATION LAYER: Prevent invalid/placeholder data
        # ============================================================
        
        # Validate price
        if price <= 0 or price < 1.0:
            logger.error(f"❌ VALIDATION FAILED: Invalid price ${price:.2f}. Must be > $1.00")
            return
        
        if price < 100 and symbol == "BTC-PERP":
            logger.error(f"❌ VALIDATION FAILED: Unrealistic BTC price ${price:.2f}. Expected > $10,000")
            return
        
        # Validate quantity
        if quantity <= 0:
            logger.error(f"❌ VALIDATION FAILED: Invalid quantity {quantity}. Must be > 0")
            return
        
        if quantity < 0.001 and market_type == "perp":
            logger.error(f"❌ VALIDATION FAILED: Quantity {quantity} below Drift minimum (0.001)")
            return
        
        # Validate side
        side_normalized = side.upper()
        if side_normalized not in ['BUY', 'SELL', 'CLOSE']:
            logger.error(f"❌ VALIDATION FAILED: Invalid side '{side}'. Must be BUY/SELL/CLOSE")
            return
        
        # Validate transaction signature (should be non-empty for executed trades)
        if not tx_signature or tx_signature == "":
            logger.warning(f"⚠️  WARNING: Missing tx_signature for {side_normalized} {symbol}")
        
        # Validate risk levels for entry trades
        if side_normalized in ['BUY', 'SELL']:
            if sl <= 0 or tp <= 0:
                logger.warning(f"⚠️  WARNING: Missing stop loss or take profit levels")
            
            # For BUY: SL should be < entry price, TP should be > entry price
            if side_normalized == 'BUY':
                if sl > price:
                    logger.error(f"❌ VALIDATION FAILED: BUY stop loss ${sl:.2f} > entry price ${price:.2f}")
                    return
                if tp < price:
                    logger.error(f"❌ VALIDATION FAILED: BUY take profit ${tp:.2f} < entry price ${price:.2f}")
                    return
            
            # For SELL: SL should be > entry price, TP should be < entry price
            elif side_normalized == 'SELL':
                if sl < price:
                    logger.error(f"❌ VALIDATION FAILED: SELL stop loss ${sl:.2f} < entry price ${price:.2f}")
                    return
                if tp > price:
                    logger.error(f"❌ VALIDATION FAILED: SELL take profit ${tp:.2f} > entry price ${price:.2f}")
                    return
        
        # SAFEGUARD: Ensure price is always positive (already checked above)
        if price < 0:
            logger.error(f"❌ VALIDATION FAILED: Negative price detected (${price:.2f})")
            return
        
        # ============================================================
        # Data passes all validation checks
        # ============================================================
        logger.debug(f"✅ Trade validation passed: {side_normalized} {quantity} {symbol} @ ${price:.2f}")
        
        # Calculate net P&L after Drift fees and funding
        if side.upper() == 'BUY' or side.upper() == 'SELL':
            # Entry trade - calculate entry fee
            entry_fee = price * quantity * taker_fee_rate
            net_entry = pnl - entry_fee if pnl > 0 else pnl - entry_fee
        elif side.upper() == 'CLOSE':
            # Close trade - calculate close fee + cumulative funding
            close_fee = price * quantity * taker_fee_rate
            total_costs = fee + close_fee + cumulative_funding
            net_pnl_after_fees = pnl - total_costs
            logger.debug(f"Close P&L breakdown: Gross=${pnl:.2f} - Fees=${total_costs:.2f} = Net=${net_pnl_after_fees:.2f}")
        else:
            net_pnl_after_fees = pnl
        
        # Prepare comprehensive trade data
        trade_data = {
            # Core identification
            'symbol': symbol,
            'market_index': market_index,
            'market_type': market_type,
            # Order details
            'side': side,
            'order_type': order_type,
            'price': price,
            'quantity': quantity,
            'fee': fee,
            'slippage_bps': slippage_bps,
            # Risk management
            'sl': sl,
            'tp': tp,
            # Trade outcome
            'pnl': pnl,
            'unrealized_pnl': unrealized_pnl,
            'status': status,
            'duration_seconds': duration_seconds,
            # Account context
            'account_equity': account_equity,
            'leverage': leverage,
            'sub_account_id': sub_account_id,
            # Strategy metadata
            'strategy_id': strategy_id,
            'signal_confidence': signal_confidence,
            'signal_type': signal_type,
            # Blockchain data
            'tx_signature': tx_signature,
            'slot': slot,
            'block_time': block_time,
            # Execution quality
            'oracle_price_at_entry': oracle_price_at_entry,
            'execution_latency_ms': execution_latency_ms,
            'bot_version': bot_version,
            'env': env,
            # Drift-specific costs
            'funding_paid': funding_paid,
            'cumulative_funding': cumulative_funding,
            'entry_hold_minutes': entry_hold_minutes,
            'taker_fee_rate': taker_fee_rate,
            'maker_fee_rate': maker_fee_rate,
            'net_pnl_after_fees': net_pnl_after_fees
        }
        
        # Convert timestamp to pandas-compatible format
        pd_timestamp = pd.Timestamp(timestamp)
        if hasattr(self.trades_info.index, 'tz') and self.trades_info.index.tz is not None:
            pd_timestamp = pd_timestamp.tz_convert(self.trades_info.index.tz)
        
        # Add to main dataframe
        self.trades_info.loc[pd_timestamp] = trade_data
        
        # Add to session tracking
        trade_data['timestamp'] = timestamp
        self.session_trades.append(trade_data)
        
        # ============================================================
        # AUDIT LOGGING: Log complete trade data for history
        # ============================================================
        logger.info(f"")
        logger.info(f"{'='*80}")
        logger.info(f"📊 TRADE RECORDED: {side_normalized.upper()} {quantity} {symbol}")
        logger.info(f"{'='*80}")
        logger.info(f"Timestamp: {timestamp.isoformat()}")
        logger.info(f"Market: {symbol} (Market Index: {market_index}, Type: {market_type})")
        logger.info(f"Side: {side_normalized} | Order Type: {order_type}")
        logger.info(f"Price: ${price:.2f} | Quantity: {quantity:.8f}")
        logger.info(f"Risk Levels: SL=${sl:.2f} | TP=${tp:.2f}")
        
        if side_normalized == 'CLOSE':
            logger.info(f"P&L Summary:")
            logger.info(f"  Gross P&L: ${pnl:.2f}")
            logger.info(f"  Entry Fee: ${fee/2:.4f} | Close Fee: ${fee/2:.4f}")
            logger.info(f"  Funding Paid: ${funding_paid:.4f}")
            logger.info(f"  Net P&L After Fees: ${net_pnl_after_fees:.2f}")
            logger.info(f"  Hold Duration: {entry_hold_minutes:.1f} minutes")
        
        logger.info(f"Account Context:")
        logger.info(f"  Account Equity: ${account_equity:.2f}")
        logger.info(f"  Leverage: {leverage}x")
        logger.info(f"  Sub-Account: {sub_account_id}")
        
        logger.info(f"Execution Quality:")
        logger.info(f"  Oracle Price: ${oracle_price_at_entry:.2f}")
        logger.info(f"  Slippage: {slippage_bps:.1f} bps")
        logger.info(f"  Latency: {execution_latency_ms:.0f} ms")
        
        logger.info(f"On-Chain Data:")
        logger.info(f"  TX Signature: {tx_signature}")
        logger.info(f"  Slot: {slot}")
        logger.info(f"  Block Time: {block_time}")
        
        logger.info(f"Environment: {env} | Bot v{bot_version}")
        logger.info(f"{'='*80}")
        logger.info(f"")
    
    def save_trades(self):
        """Save trades to CSV"""
        try:
            self.trades_info.to_csv(TRADES_FILE)
            logger.debug(f"Trades saved to {TRADES_FILE}")
        except Exception as e:
            logger.error(f"Error saving trades: {e}")
    
    def get_trades(self, symbol: Optional[str] = None, days: Optional[int] = None) -> pd.DataFrame:
        """
        Get trades with optional filtering
        
        Args:
            symbol: Filter by symbol
            days: Get trades from last N days
            
        Returns:
            Filtered DataFrame of trades
        """
        df = self.trades_info.copy()
        
        if symbol:
            df = df[df['symbol'] == symbol]
        
        if days and not df.empty:
            try:
                # Use centralized timezone - ensure consistent datetime types
                tz_str = 'UTC' if TIMEZONE.tzname(None) == 'UTC' else str(TIMEZONE)
                cutoff_date = pd.Timestamp.now(tz=tz_str) - pd.Timedelta(days=days)
                
                # Convert cutoff_date to same timezone as DataFrame index
                if hasattr(df.index, 'tz') and df.index.tz is not None:
                    cutoff_date = cutoff_date.tz_convert(df.index.tz)
                else:
                    # Ensure both are timezone-naive if index is naive
                    cutoff_date = cutoff_date.tz_localize(None)
                
                df = df[df.index >= cutoff_date]
            except Exception as e:
                logger.warning(f"Error filtering trades by date: {e}")
                # Return empty DataFrame if filtering fails
                pass
        
        return df
    
    def get_session_trades(self) -> list:
        """Get trades from current session"""
        return self.session_trades.copy()
    
    def calculate_pnl(self, symbol: Optional[str] = None) -> Dict[str, float]:
        """
        Calculate P&L for trades
        
        Args:
            symbol: Calculate P&L for specific symbol, None for all
            
        Returns:
            Dictionary with P&L metrics
        """
        df = self.get_trades(symbol=symbol)
        
        if df.empty:
            return {
                'realized_pnl': 0.0,
                'total_trades': 0,
                'winning_trades': 0,
                'losing_trades': 0,
                'win_rate': 0.0
            }
        
        # Enhanced P&L calculation for BUY/SELL/CLOSE trade format
        realized_pnl = 0.0
        winning_trades = 0
        losing_trades = 0
        completed_trades = 0
        
        # Group by symbol for P&L calculation
        symbols = df['symbol'].unique() if symbol is None else [symbol]
        
        for sym in symbols:
            sym_trades = df[df['symbol'] == sym].copy()
            sym_trades = sym_trades.sort_index()
            
            position_stack = []  # Track open positions
            
            for _, trade in sym_trades.iterrows():
                side = trade['side'].upper()  # Normalize to uppercase
                
                if side in ['BUY', 'SELL']:
                    # Opening position - store entry details
                    position_stack.append({
                        'side': side,
                        'price': trade['price'],
                        'quantity': trade['quantity'],
                        'timestamp': trade.name
                    })
                
                elif side == 'CLOSE' and position_stack:
                    # Closing position
                    last_position = position_stack.pop()
                    
                    # Use the actual P&L if recorded in the CLOSE trade
                    if pd.notna(trade.get('pnl')) and trade.get('pnl') != 0:
                        # P&L was calculated and stored during closing
                        trade_pnl = float(trade.get('pnl'))
                        logger.debug(f"Using recorded P&L: ${trade_pnl:.2f}")
                    else:
                        # Fallback: calculate from entry/close prices
                        entry_price = last_position['price']
                        close_price = trade['price']
                        qty = trade['quantity'] if trade['quantity'] > 0 else last_position['quantity']
                        
                        # Skip if close price is placeholder (0.001)
                        if close_price < 1.0:
                            logger.warning(f"⚠️ Invalid close price ({close_price}), skipping P&L calculation")
                            continue
                        
                        if last_position['side'] == 'BUY':
                            # LONG: profit = (close - entry) * qty
                            trade_pnl = qty * (close_price - entry_price)
                        else:  # SELL
                            # SHORT: profit = (entry - close) * qty
                            trade_pnl = qty * (entry_price - close_price)
                        
                        logger.debug(f"Calculated P&L: ${trade_pnl:.2f} ({last_position['side']} @ {entry_price:.2f} → {close_price:.2f})")
                    
                    realized_pnl += trade_pnl
                    completed_trades += 1
                    
                    if trade_pnl > 0:
                        winning_trades += 1
                    else:
                        losing_trades += 1
        
        win_rate = (winning_trades / completed_trades * 100) if completed_trades > 0 else 0
        
        return {
            'realized_pnl': realized_pnl,
            'total_trades': completed_trades,
            'winning_trades': winning_trades,
            'losing_trades': losing_trades,
            'win_rate': win_rate
        }
    
    def print_trades(self, days: Optional[int] = None):
        """Print recent trades"""
        df = self.get_trades(days=days)
        
        if df.empty:
            print("No trades found")
            return
        
        print(f"\n=== Trading History ({'Last ' + str(days) + ' days' if days else 'All time'}) ===")
        print(df.to_string())
        
        # Print P&L summary
        pnl_stats = self.calculate_pnl()
        print(f"\n=== P&L Summary ===")
        print(f"Realized P&L: ${pnl_stats['realized_pnl']:.2f}")
        print(f"Total Trades: {pnl_stats['total_trades']}")
        print(f"Winning Trades: {pnl_stats['winning_trades']}")
        print(f"Losing Trades: {pnl_stats['losing_trades']}")
        print(f"Win Rate: {pnl_stats['win_rate']:.1f}%")
    
    def print_session_summary(self):
        """Print summary of current session trades"""
        if not self.session_trades:
            print("No trades in current session")
            return
        
        print(f"\n=== Session Summary ({len(self.session_trades)} trades) ===")
        for trade in self.session_trades:
            print(f"{trade['timestamp'].strftime('%H:%M:%S')} - "
                  f"{trade['side'].upper()} {trade['quantity']} {trade['symbol']} @ {trade['price']}")
    
    def export_trades(self, filename: Optional[str] = None, format: str = 'csv'):
        """
        Export trades to file
        
        Args:
            filename: Output filename, None for auto-generated
            format: 'csv' or 'json'
        """
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"drift_trades_{timestamp}.{format}"
        
        try:
            if format.lower() == 'csv':
                self.trades_info.to_csv(filename)
            elif format.lower() == 'json':
                self.trades_info.to_json(filename, orient='index', date_format='iso')
            
            logger.info(f"Trades exported to {filename}")
            
        except Exception as e:
            logger.error(f"Error exporting trades: {e}")


        # Backwards compatibility alias
PortfolioTracker = DriftPortfolioTracker


# ============================================================================
# Drift-Specific P&L Calculation Methods
# ============================================================================

class DriftPnLCalculator:
    """Calculate accurate P&L including Drift protocol-specific costs"""
    
    DEFAULT_TAKER_FEE = 0.0005  # 0.05%
    DEFAULT_MAKER_FEE = 0.0002  # 0.02%
    FUNDING_INTERVAL = 1 / 24   # Hourly funding (1/24 of day)
    
    @staticmethod
    def calculate_entry_fee(notional_value: float, is_maker: bool = False) -> float:
        """
        Calculate fee paid on entry
        
        Args:
            notional_value: price * quantity
            is_maker: True if maker order, False if taker
            
        Returns:
            Fee amount in quote currency
        """
        rate = DriftPnLCalculator.DEFAULT_MAKER_FEE if is_maker else DriftPnLCalculator.DEFAULT_TAKER_FEE
        return notional_value * rate
    
    @staticmethod
    def calculate_close_fee(notional_value: float, is_maker: bool = False) -> float:
        """Calculate fee paid on close"""
        return DriftPnLCalculator.calculate_entry_fee(notional_value, is_maker)
    
    @staticmethod
    def calculate_funding_payment(notional_value: float, funding_rate: float, hold_hours: float) -> float:
        """
        Calculate cumulative funding payments
        
        Args:
            notional_value: price * quantity
            funding_rate: 8-hour funding rate from Drift
            hold_hours: How long position was held (in hours)
            
        Returns:
            Total funding paid (negative = you paid, positive = you received)
        """
        # Funding is paid every 1 hour on Drift
        num_periods = hold_hours
        # Each period funding = notional_value * funding_rate
        total_funding = notional_value * funding_rate * num_periods
        return total_funding
    
    @staticmethod
    def calculate_realized_pnl(entry_price: float, close_price: float, quantity: float, 
                              side: str, hold_hours: float = 0.0, 
                              funding_rate: float = 0.0, is_maker: bool = False) -> Dict[str, float]:
        """
        Calculate complete realized P&L breakdown for Drift position
        
        Args:
            entry_price: Entry price per unit
            close_price: Close price per unit
            quantity: Position size
            side: 'BUY' or 'SELL'
            hold_hours: How long position was held
            funding_rate: 8-hour funding rate (positive = longs pay, negative = shorts receive)
            is_maker: True if both entry and close were maker orders
            
        Returns:
            Dictionary with complete P&L breakdown
        """
        notional_value = entry_price * quantity
        
        # Calculate gross P&L
        if side.upper() == 'BUY':
            gross_pnl = quantity * (close_price - entry_price)
        else:  # SELL
            gross_pnl = quantity * (entry_price - close_price)
        
        # Calculate all costs
        entry_fee = DriftPnLCalculator.calculate_entry_fee(notional_value, is_maker)
        close_fee = DriftPnLCalculator.calculate_close_fee(notional_value, is_maker)
        
        # Funding payment (positive = you paid, negative = you received)
        if side.upper() == 'BUY':
            funding_paid = DriftPnLCalculator.calculate_funding_payment(notional_value, funding_rate, hold_hours)
        else:  # SELL - funding direction is reversed
            funding_paid = -DriftPnLCalculator.calculate_funding_payment(notional_value, funding_rate, hold_hours)
        
        total_costs = entry_fee + close_fee + funding_paid
        net_pnl = gross_pnl - total_costs
        
        return {
            'gross_pnl': gross_pnl,
            'entry_fee': entry_fee,
            'close_fee': close_fee,
            'funding_paid': funding_paid,
            'total_costs': total_costs,
            'net_pnl': net_pnl,
            'net_pnl_pct': (net_pnl / notional_value * 100) if notional_value > 0 else 0.0
        }
    
    @staticmethod
    def format_pnl_report(pnl_dict: Dict[str, float]) -> str:
        """Format P&L calculation as readable report"""
        return f"""
P&L Breakdown:
  Gross P&L:        ${pnl_dict['gross_pnl']:>10.2f}
  Entry Fee:        ${pnl_dict['entry_fee']:>10.2f}
  Close Fee:        ${pnl_dict['close_fee']:>10.2f}
  Funding Paid:     ${pnl_dict['funding_paid']:>10.2f}
  ─────────────────────────
  Total Costs:      ${pnl_dict['total_costs']:>10.2f}
  NET P&L:          ${pnl_dict['net_pnl']:>10.2f} ({pnl_dict['net_pnl_pct']:+.2f}%)
"""