"""
Order execution handler for interacting with Drift Protocol
"""
import asyncio
import time
import pandas as pd
from datetime import datetime
from typing import Optional, Tuple, Dict, Any, List
from ..config import (
    SOLANA_RPC_URL, PRIVATE_KEY, DRIFT_ENV, SUB_ACCOUNT_ID,
    TX_COMPUTE_UNITS, TX_COMPUTE_UNIT_PRICE, get_market_index_by_symbol
)
from ..logger import logger

try:
    from solana.rpc.async_api import AsyncClient
    from solders.keypair import Keypair
    from anchorpy import Wallet
    from driftpy.drift_client import DriftClient
    from driftpy.account_subscription_config import AccountSubscriptionConfig
    from driftpy.types import (
        OrderParams, OrderType, PositionDirection, MarketType,
        TxParams, PostOnlyParams, OrderTriggerCondition
    )
    from driftpy.constants.numeric_constants import BASE_PRECISION, PRICE_PRECISION
    from driftpy.keypair import load_keypair
except ImportError as e:
    logger.error(f"Failed to import Drift dependencies: {e}")
    raise


class DriftOrderExecutor:
    def __init__(self, private_key: str, sub_account_id: int = SUB_ACCOUNT_ID):
        """
        Initialize the Drift order executor
        
        Args:
            private_key: Base58 encoded private key or path to keypair file
            sub_account_id: Drift subaccount ID to use
        """
        self.private_key = private_key
        self.sub_account_id = sub_account_id
        # Use longer timeout for slow RPC endpoints
        import httpx
        self.connection = AsyncClient(
            SOLANA_RPC_URL,
            timeout=httpx.Timeout(30.0, connect=10.0)  # 30s read, 10s connect timeout
        )
        self.drift_client: Optional[DriftClient] = None
        self._initialized = False
        self._init_retries = 3  # Number of retry attempts
        
    async def initialize(self):
        """Initialize Drift client and wallet with retry logic"""
        if self._initialized:
            return
        
        for attempt in range(self._init_retries):
            try:
                logger.info(f"Initializing Drift executor (attempt {attempt + 1}/{self._init_retries})...")
                
                # Load keypair
                if self.private_key.startswith('/') or self.private_key.startswith('./'):
                    # File path
                    keypair = load_keypair(self.private_key)
                else:
                    # Base58 string
                    keypair = Keypair.from_base58_string(self.private_key)
                
                wallet = Wallet(keypair)
                
                # Initialize Drift client
                self.drift_client = DriftClient(
                    connection=self.connection,
                    wallet=wallet,
                    env=DRIFT_ENV,
                    account_subscription=AccountSubscriptionConfig("websocket"),
                    tx_params=TxParams(
                        compute_units=TX_COMPUTE_UNITS,
                        compute_units_price=TX_COMPUTE_UNIT_PRICE
                    )
                )
                
                # Subscribe with timeout
                try:
                    await asyncio.wait_for(self.drift_client.subscribe(), timeout=30.0)
                except asyncio.TimeoutError:
                    logger.warning(f"Drift subscription timed out on attempt {attempt + 1}")
                    if attempt < self._init_retries - 1:
                        await asyncio.sleep(2 ** attempt)  # Exponential backoff
                        continue
                    raise
                
                # Add user subaccount if it doesn't exist
                try:
                    await self.drift_client.add_user(self.sub_account_id)
                except Exception as e:
                    logger.debug(f"Subaccount {self.sub_account_id} may already exist: {e}")
                
                self._initialized = True
                logger.info(f"✅ Drift executor initialized for wallet: {keypair.pubkey()}")
                return
                
            except Exception as e:
                logger.warning(f"Attempt {attempt + 1} failed: {e}")
                if attempt < self._init_retries - 1:
                    wait_time = 2 ** attempt
                    logger.info(f"Retrying in {wait_time}s...")
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"❌ Failed to initialize Drift executor after {self._init_retries} attempts")
                    raise
    
    async def get_account_balance(self) -> float:
        """Get total available collateral for trading"""
        if not self._initialized:
            await self.initialize()
            
        try:
            user = self.drift_client.get_user()
            
            # Use free collateral instead of just USDC balance
            # This includes all collateral assets (USDC + SOL value, etc.)
            free_collateral = user.get_free_collateral()
            balance = float(free_collateral) / PRICE_PRECISION
            
            logger.debug(f"Account balance: Free collateral = {balance:.2f} USD")
            return max(0, balance)
            
        except Exception as e:
            logger.error(f"Error getting account balance: {e}")
            return 0.0
    
    def get_account_cash(self) -> float:
        """Synchronous wrapper for getting account balance"""
        if not self._initialized:
            # Run initialization if needed
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # We're already in an async context, need to handle differently
                return 1000.0  # Return a default value
            else:
                return asyncio.run(self.get_account_balance())
        
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Create a task to run in the existing loop
            return 1000.0  # Return default for now
        else:
            return asyncio.run(self.get_account_balance())
    
    async def get_open_position(self) -> pd.DataFrame:
        """Get all open positions as DataFrame"""
        if not self._initialized:
            await self.initialize()
            
        try:
            user = self.drift_client.get_user()
            positions = []
            
            # Get perpetual positions
            perp_positions = user.get_user_account().perp_positions
            for pos in perp_positions:
                if pos.base_asset_amount != 0:  # Has position
                    # Calculate entry price with proper Drift scaling
                    # Base asset (e.g., BTC) is in BASE_PRECISION (1e9)
                    # Quote entry amount (USD) is in PRICE_PRECISION (1e6)
                    try:
                        base_amt = float(pos.base_asset_amount) / BASE_PRECISION
                        quote_amt = float(pos.quote_entry_amount) / PRICE_PRECISION
                        
                        if base_amt != 0:
                            entry_price = abs(quote_amt / base_amt)
                        else:
                            entry_price = 0
                        
                        # Sanity check for BTC-PERP and similar high-value assets
                        if entry_price < 100 or entry_price > 200000:
                            logger.warning(f"⚠️ Abnormal entry price detected for MARKET_{pos.market_index}: {entry_price}")
                            # Don't override, let it through for debugging but log it
                    except Exception as e:
                        logger.error(f"❌ Error computing entry price for MARKET_{pos.market_index}: {e}")
                        entry_price = 0
                    
                    # CRITICAL: Keep sign for position direction (positive = LONG, negative = SHORT)
                    qty_signed = float(pos.base_asset_amount) / BASE_PRECISION
                    
                    positions.append({
                        'symbol': f"MARKET_{pos.market_index}",
                        'market_index': pos.market_index,
                        'qty': qty_signed,  # Keep sign: positive=LONG, negative=SHORT
                        'market_type': 'perp',
                        'entry_price': entry_price,
                        'direction': 'LONG' if qty_signed > 0 else 'SHORT',  # Explicit direction
                    })
            
            # Get spot positions (excluding USDC)
            spot_positions = user.get_user_account().spot_positions
            for pos in spot_positions:
                if pos.market_index != 0 and pos.scaled_balance != 0:  # Not USDC and has balance
                    positions.append({
                        'symbol': f"SPOT_{pos.market_index}",
                        'market_index': pos.market_index,
                        'qty': float(pos.scaled_balance) / PRICE_PRECISION,
                        'market_type': 'spot',
                        'entry_price': 0,  # Not tracked for spot
                    })
            
            return pd.DataFrame(positions)
            
        except Exception as e:
            logger.error(f"Error getting positions: {e}")
            return pd.DataFrame()
    
    async def get_open_positions(self) -> List[Dict]:
        """
        Get all open positions as a list of dictionaries
        
        Returns:
            List of position info dictionaries
        """
        try:
            positions_df = await self.get_open_position()
            return positions_df.to_dict('records') if not positions_df.empty else []
        except Exception as e:
            logger.error(f"Error getting open positions list: {e}")
            return []
    
    async def get_open_orders(self) -> pd.DataFrame:
        """Get all open orders as DataFrame"""
        if not self._initialized:
            await self.initialize()
            
        try:
            user = self.drift_client.get_user()
            orders = user.get_open_orders()
            
            order_list = []
            for order in orders:
                order_list.append({
                    'id': order.order_id,
                    'symbol': f"{'PERP' if order.market_type == MarketType.Perp() else 'SPOT'}_{order.market_index}",
                    'market_index': order.market_index,
                    'market_type': 'perp' if order.market_type == MarketType.Perp() else 'spot',
                    'direction': 'buy' if order.direction == PositionDirection.Long() else 'sell',
                    'base_asset_amount': float(order.base_asset_amount) / BASE_PRECISION,
                    'price': float(order.price) / PRICE_PRECISION,
                    'order_type': str(order.order_type),
                })
            
            return pd.DataFrame(order_list)
            
        except Exception as e:
            logger.error(f"Error getting orders: {e}")
            return pd.DataFrame()
    
    async def get_position_info(self, symbol: str) -> dict:
        """
        Get position information for a specific symbol
        
        Args:
            symbol: Market symbol (e.g., "SOL-PERP")
            
        Returns:
            Dictionary with position information
        """
        if not self._initialized:
            await self.initialize()
        
        try:
            user = self.drift_client.get_user()
            
            # Parse market index from symbol
            market_index = get_market_index_by_symbol(symbol)
            
            # Get specific perp position by market index
            position = user.get_perp_position(market_index)
            
            if position and position.base_asset_amount != 0:
                # Calculate entry price with proper Drift scaling
                try:
                    base_amt = float(position.base_asset_amount) / BASE_PRECISION
                    quote_amt = float(position.quote_entry_amount) / PRICE_PRECISION
                    
                    if base_amt != 0:
                        entry_price = abs(quote_amt / base_amt)
                    else:
                        entry_price = 0
                    
                    # Sanity check
                    if entry_price < 100 or entry_price > 200000:
                        logger.warning(f"⚠️ Abnormal entry price detected for {symbol}: {entry_price}")
                except Exception as e:
                    logger.error(f"❌ Error computing entry price for {symbol}: {e}")
                    entry_price = 0
                
                return {
                    'symbol': symbol,
                    'market_index': market_index,
                    'size': abs(float(position.base_asset_amount) / BASE_PRECISION),
                    'side': 'long' if position.base_asset_amount > 0 else 'short',
                    'entry_price': entry_price,
                    'unrealized_pnl': float(position.quote_asset_amount) / PRICE_PRECISION,
                    'open': True
                }
            
            # No position found
            return {
                'symbol': symbol,
                'market_index': market_index,
                'size': 0.0,
                'side': 'none',
                'entry_price': 0.0,
                'unrealized_pnl': 0.0,
                'open': False
            }
            
        except Exception as e:
            logger.error(f"Error getting position info for {symbol}: {e}")
            return {
                'symbol': symbol,
                'market_index': 0,
                'size': 0.0,
                'side': 'none',
                'entry_price': 0.0,
                'unrealized_pnl': 0.0,
                'open': False
            }
    
    async def place_market_order(self, symbol: str, quantity: float, side: str) -> Optional[str]:
        """
        Place a market order
        
        Args:
            symbol: Market symbol (e.g., "SOL-PERP")
            quantity: Order quantity
            side: "BUY" or "SELL"
            
        Returns:
            Transaction signature if successful, None otherwise
        """
        if not self._initialized:
            await self.initialize()
            
        try:
            market_index = get_market_index_by_symbol(symbol)
            direction = PositionDirection.Long() if side.upper() == "BUY" else PositionDirection.Short()
            market_type = MarketType.Perp() if symbol.endswith("-PERP") else MarketType.Spot()
            
            
            # Add debugging info
            base_asset_amount = int(quantity * BASE_PRECISION)
            logger.info(f"Order debug: symbol={symbol}, quantity={quantity}, BASE_PRECISION={BASE_PRECISION}, base_asset_amount={base_asset_amount}")
            
            order_params = OrderParams(
                order_type=OrderType.Market(),
                market_type=market_type,
                direction=direction,
                user_order_id=int(time.time()) % 255,  # Keep order ID within struct bounds (0-255)
                base_asset_amount=base_asset_amount,
                market_index=market_index,
                reduce_only=False,
            )
            
            tx_sig = await self.drift_client.place_orders([order_params])
            
            if tx_sig:
                logger.info(f"Market order placed: {symbol} {side} {quantity}, tx: {tx_sig}")
                
                # Wait a moment for execution then get actual execution details
                await asyncio.sleep(2)  # Allow time for order processing
                execution_details = await self.get_execution_details(symbol, tx_sig)
                if execution_details:
                    actual_price = execution_details.get('execution_price', 'market')
                    actual_qty = execution_details.get('execution_quantity', 0)
                    logger.info(f"📊 EXECUTION DETAILS: {symbol} {side} - Intended: {quantity}@market | Actual: {actual_qty}@{actual_price}")
                    
                    # Check if order was actually filled
                    if actual_qty == 0:
                        logger.error(f"❌ ORDER REJECTED! Actual quantity = 0")
                        logger.error(f"💰 Possible reasons:")
                        logger.error(f"   1. Insufficient margin/collateral")
                        logger.error(f"   2. Position size exceeds account leverage limits")
                        logger.error(f"   3. Market conditions preventing fill")
                        logger.error(f"💡 Solutions:")
                        logger.error(f"   • Reduce POSITION_PCT from 0.5 to 0.3 in config")
                        logger.error(f"   • Reduce LEVERAGE_MULTIPLIER from 2.0 to 1.5")
                        logger.error(f"   • Check Drift UI for pending orders or margin issues")
                        return None  # Return None to indicate failed order
            
            return tx_sig
            
        except Exception as e:
            logger.error(f"Error placing market order for {symbol}: {e}")
            return None
    
    async def get_execution_details(self, symbol: str, tx_signature: str) -> Optional[Dict]:
        """
        Get actual execution details from a transaction
        
        Args:
            symbol: Market symbol
            tx_signature: Transaction signature to analyze
            
        Returns:
            Dictionary with execution details or None
        """
        try:
            # For CLOSE trades, we need to get current market price since position no longer exists
            # Try to get oracle price as a fallback for execution price
            market_index = get_market_index_by_symbol(symbol)
            market_type = MarketType.Perp() if symbol.endswith("-PERP") else MarketType.Spot()
            
            # Get current oracle price as best estimate for execution price
            try:
                if market_type == MarketType.Perp():
                    oracle_data = self.drift_client.get_perp_market_account(market_index)
                    if oracle_data and hasattr(oracle_data, 'amm'):
                        # Get oracle price from market
                        oracle_price = float(oracle_data.amm.historical_oracle_data.last_oracle_price) / PRICE_PRECISION
                        
                        return {
                            'execution_price': abs(oracle_price),  # Always return positive price
                            'execution_quantity': 0,  # Unknown for closed positions
                            'timestamp': datetime.now(),
                            'tx_signature': tx_signature
                        }
            except Exception as oracle_err:
                logger.warning(f"Could not get oracle price: {oracle_err}")
            
            # Fallback: Check if position still exists (for partial closes)
            recent_position = await self.get_open_position()
            if not recent_position.empty:
                # Find position for this symbol
                for _, pos in recent_position.iterrows():
                    if pos.get('symbol') == symbol or pos.get('market_index') == market_index:
                        return {
                            'execution_price': abs(pos.get('entry_price', 0.001)),  # Always positive
                            'execution_quantity': abs(pos.get('qty', 0)),
                            'timestamp': datetime.now(),
                            'tx_signature': tx_signature
                        }
            
            logger.warning(f"Could not get execution details for {symbol} tx: {tx_signature}")
            return None
            
        except Exception as e:
            logger.error(f"Error getting execution details: {e}")
            return None
    
    async def place_stop_order(self, symbol: str, stop_price: float, quantity: float, side: str) -> Optional[str]:
        """
        Place a stop loss order
        
        Args:
            symbol: Market symbol
            stop_price: Stop trigger price
            quantity: Order quantity
            side: "BUY" or "SELL"
            
        Returns:
            Transaction signature if successful
        """
        if not self._initialized:
            await self.initialize()
            
        try:
            market_index = get_market_index_by_symbol(symbol)
            direction = PositionDirection.Long() if side.upper() == "BUY" else PositionDirection.Short()
            market_type = MarketType.Perp() if symbol.endswith("-PERP") else MarketType.Spot()
            
            # Determine trigger condition based on side
            trigger_condition = (
                OrderTriggerCondition.Below() if side.upper() == "SELL" 
                else OrderTriggerCondition.Above()
            )
            
            order_params = OrderParams(
                order_type=OrderType.TriggerMarket(),
                market_type=market_type,
                direction=direction,
                user_order_id=int(time.time()) % 255,  # Keep order ID within struct bounds
                base_asset_amount=int(quantity * BASE_PRECISION),
                market_index=market_index,
                trigger_price=int(stop_price * PRICE_PRECISION),
                trigger_condition=trigger_condition,
                reduce_only=True,  # Stop orders are typically reduce-only
            )
            
            tx_sig = await self.drift_client.place_orders([order_params])
            logger.info(f"Stop order placed: {symbol} {side} {quantity} @ {stop_price}, tx: {tx_sig}")
            return tx_sig
            
        except Exception as e:
            logger.error(f"Error placing stop order for {symbol}: {e}")
            return None
    
    async def close_position(self, symbol: str) -> Tuple[bool, Optional[float], Optional[float]]:
        """
        Close a position by market order
        
        Args:
            symbol: Market symbol
            
        Returns:
            Tuple of (success, quantity_closed, close_price)
        """
        if not self._initialized:
            await self.initialize()
            
        try:
            # Get current position
            positions_df = await self.get_open_position()
            market_index = get_market_index_by_symbol(symbol)
            
            # Find position for this market
            market_positions = positions_df[positions_df['market_index'] == market_index]
            
            if market_positions.empty:
                logger.warning(f"No position found for {symbol}")
                return False, None, None
            
            position = market_positions.iloc[0]
            current_qty = position['qty']
            
            if current_qty == 0:
                return False, None, None
            
            # Determine close direction (opposite of current position)
            close_side = "SELL" if current_qty > 0 else "BUY"
            close_qty = abs(current_qty)
            
            # Get current price for reporting
            if symbol.endswith("-PERP"):
                oracle_data = self.drift_client.get_oracle_price_data_for_perp_market(market_index)
            else:
                oracle_data = self.drift_client.get_oracle_price_data_for_spot_market(market_index)
            
            current_price = float(oracle_data.price) / PRICE_PRECISION if oracle_data else 0.0
            
            # Place closing market order
            tx_sig = await self.place_market_order(symbol, close_qty, close_side)
            
            if tx_sig:
                logger.info(f"Position closed: {symbol} {close_qty} @ ~{current_price}")
                return True, close_qty, current_price
            
            return False, None, None
            
        except Exception as e:
            logger.error(f"Error closing position for {symbol}: {e}")
            return False, None, None
    
    async def close_order(self, symbol: str):
        """Cancel all open orders for a symbol"""
        if not self._initialized:
            await self.initialize()
            
        try:
            market_index = get_market_index_by_symbol(symbol)
            
            # Cancel all orders for this market
            await self.drift_client.cancel_orders(
                market_index=market_index,
                market_type=MarketType.Perp() if symbol.endswith("-PERP") else MarketType.Spot()
            )
            
            logger.info(f"All orders cancelled for {symbol}")
            
        except Exception as e:
            logger.error(f"Error cancelling orders for {symbol}: {e}")
    
    async def cleanup(self):
        """Clean up resources"""
        if self.drift_client and self._initialized:
            try:
                await self.drift_client.unsubscribe()
                logger.info("Drift executor cleaned up")
            except Exception as e:
                logger.error(f"Error during cleanup: {e}")


# Backwards compatibility alias
OrderExecutor = DriftOrderExecutor