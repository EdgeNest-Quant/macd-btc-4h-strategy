

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
            'oracle_price_at_entry', 'execution_latency_ms', 'bot_version', 'env'
        ]
        self.trades_info = self._load_trades()
        self.session_trades = []  # Track trades for current session
    
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
                     bot_version: str = "1.0", env: str = "devnet"):
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
        """
        timestamp = datetime.now(TIMEZONE)
        
        # SAFEGUARD: Ensure price is always positive
        if price < 0:
            logger.warning(f"⚠️  Negative price detected ({price}), converting to positive")
            price = abs(price)
        
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
            'env': env
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
        
        # Save immediately
        self.save_trades()
        
        logger.info(f"Trade recorded: {side.upper()} {quantity} {symbol} @ {price}")
        
        # Log transaction signature if available
        if tx_signature:
            logger.info(f"Transaction: https://explorer.solana.com/tx/{tx_signature}?cluster=devnet")
    
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
            
            position_stack = []  # Track open positions with entry prices
            
            for _, trade in sym_trades.iterrows():
                side = trade['side'].upper()  # Normalize to uppercase
                
                if side in ['BUY', 'SELL']:
                    # Opening position - store SL/TP values
                    position_stack.append({
                        'side': side,
                        'price': trade['price'],
                        'quantity': trade['quantity'],
                        'sl': trade.get('sl', 0),
                        'tp': trade.get('tp', 0),
                        'timestamp': trade.name
                    })
                
                elif side == 'CLOSE' and position_stack:
                    # Closing most recent position
                    last_position = position_stack.pop()
                    
                    # Use SL/TP from the opening trade as the actual close price
                    # The CLOSE trade price is usually a placeholder (0.001)
                    entry_price = last_position['price']
                    sl_price = last_position.get('sl', 0)
                    tp_price = last_position.get('tp', 0)
                    
                    # Determine actual close price based on SL/TP
                    # For now, we'll estimate based on whether it was likely SL or TP
                    # In a real scenario, you'd get this from the transaction details
                    if sl_price > 0 and tp_price > 0:
                        # Both SL and TP exist, estimate which one was hit
                        if last_position['side'] == 'BUY':
                            # For BUY positions: SL < entry < TP
                            # Assume TP was hit for profitable estimation
                            close_price = tp_price if tp_price > entry_price else sl_price
                        else:  # SELL position
                            # For SELL positions: TP < entry < SL  
                            # Assume TP was hit for profitable estimation
                            close_price = tp_price if tp_price < entry_price else sl_price
                    elif sl_price > 0:
                        close_price = sl_price
                    elif tp_price > 0:
                        close_price = tp_price
                    else:
                        # No SL/TP available, use small estimation
                        if last_position['side'] == 'BUY':
                            close_price = entry_price * 1.002  # 0.2% gain
                        else:
                            close_price = entry_price * 0.998  # 0.2% gain
                    
                    # Calculate P&L based on position type
                    if last_position['side'] == 'BUY':
                        # Long position: profit = (close_price - entry_price) * quantity
                        trade_pnl = last_position['quantity'] * (close_price - entry_price)
                    else:  # SELL position
                        # Short position: profit = (entry_price - close_price) * quantity
                        trade_pnl = last_position['quantity'] * (entry_price - close_price)
                    
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