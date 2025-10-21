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
        self.connection = AsyncClient(SOLANA_RPC_URL)
        self.drift_client: Optional[DriftClient] = None
        self._initialized = False
        
    async def initialize(self):
        """Initialize Drift client and wallet"""
        if self._initialized:
            return
            
        try:
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
            
            await self.drift_client.subscribe()
            
            # Add user subaccount if it doesn't exist
            try:
                await self.drift_client.add_user(self.sub_account_id)
            except Exception as e:
                logger.debug(f"Subaccount {self.sub_account_id} may already exist: {e}")
            
            self._initialized = True
            logger.info(f"Drift executor initialized for wallet: {keypair.pubkey()}")
            
        except Exception as e:
            logger.error(f"Failed to initialize Drift executor: {e}")
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
                    positions.append({
                        'symbol': f"MARKET_{pos.market_index}",
                        'market_index': pos.market_index,
                        'qty': float(pos.base_asset_amount) / BASE_PRECISION,
                        'market_type': 'perp',
                        'entry_price': float(pos.quote_entry_amount) / float(pos.base_asset_amount) if pos.base_asset_amount != 0 else 0,
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
                return {
                    'symbol': symbol,
                    'market_index': market_index,
                    'size': float(position.base_asset_amount) / BASE_PRECISION,
                    'side': 'long' if position.base_asset_amount > 0 else 'short',
                    'entry_price': float(position.quote_entry_amount) / float(position.base_asset_amount) if position.base_asset_amount != 0 else 0,
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
                    actual_price = execution_details.get('execution_price', 'Unknown')
                    actual_qty = execution_details.get('execution_quantity', quantity)
                    logger.info(f"📊 EXECUTION DETAILS: {symbol} {side} - Intended: {quantity}@{quantity*100000 if side=='BUY' else 'market'} | Actual: {actual_qty}@{actual_price}")
            
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
            
#         Returns:
#             int: 1 if no market order exists, 0 if exists
#         """
#         order_df = self.get_open_orders()
#         if not order_df.empty:
#             order_df = order_df[order_df['order_type'] == 'market']
#             if not order_df.empty and (ticker in order_df['symbol'].to_list()):
#                 return 0
#         return 1
    
#     def place_market_order(self, symbol, quantity, side):
#         """
#         Place a market order
        
#         Args:
#             symbol (str): Ticker symbol
#             quantity (float): Quantity to trade
#             side (OrderSide): BUY or SELL
            
#         Returns:
#             order object or None
#         """
#         if self.check_market_order_placed(symbol):
#             try:
#                 market_order_data = MarketOrderRequest(
#                     symbol=symbol,
#                     qty=quantity,
#                     side=side,
#                     time_in_force=TimeInForce.GTC
#                 )
                
#                 market_order = self.trading_client.submit_order(order_data=market_order_data)
#                 print(market_order)
#                 logger.info(f"Order placed: {side} {quantity} {symbol}")
#                 return market_order
#             except Exception as e:
#                 error_msg = str(e)
#                 logger.error(f"Failed to place order for {symbol}: {error_msg}")
#                 print(f"❌ Order failed: {error_msg}")
                
#                 # Parse insufficient balance error
#                 if "insufficient balance" in error_msg.lower():
#                     print(f"💡 Try reducing position size or check available balance")
                
#                 return None
#         return None
    
#     def place_stop_order(self, symbol, stop_price, quantity, side):
#         """
#         Place a stop limit order
        
#         Args:
#             symbol (str): Ticker symbol
#             stop_price (float): Stop price
#             quantity (float): Quantity
#             side (OrderSide): BUY or SELL
#         """
#         logger.info(f'Placing stop order for {quantity} of {symbol} at {stop_price}')
#         print('placing stop order')
        
#         req = StopLimitOrderRequest(
#             symbol=symbol,
#             qty=quantity,
#             side=side,
#             time_in_force=TimeInForce.GTC,
#             limit_price=round(stop_price, 2),
#             stop_price=round(stop_price, 2)
#         )
        
#         res = self.trading_client.submit_order(req)
#         print(res)
#         return res
    
#     def check_and_place_stop_orders(self, pos_df, order_df):
#         """
#         Check positions and place stop orders if needed
        
#         Args:
#             pos_df (pd.DataFrame): Positions dataframe
#             order_df (pd.DataFrame): Orders dataframe
#         """
#         if not pos_df.empty:
#             print('inside check and place stop order')
#             l1 = pos_df['symbol'].to_list()
#             print(l1)
#             print(LIST_OF_TICKERS)
            
#             l1 = list(set(l1).intersection(set([l.replace('/', '') for l in LIST_OF_TICKERS])))
#             print(l1)
            
#             for ticker in LIST_OF_TICKERS:
#                 try:
#                     t = self.trading_client.get_open_position(ticker.replace('/', ''))
#                     buy_price = float(t.avg_entry_price)
#                     quantity = abs(round(float(t.qty), 2))
#                     s = t.side
                    
#                     if s == OrderSide.BUY:
#                         s = OrderSide.SELL
#                         stop_price = buy_price * (1 - (STOP_PERC / 100))  # correct SL for long

#                     else:
#                         s = OrderSide.BUY
#                         stop_price = buy_price * (1 - (STOP_PERC / 100))  # correct SL for long


#                     if order_df.empty or (ticker not in order_df['symbol'].to_list()):
#                         self.place_stop_order(ticker, stop_price, quantity, s)
                    
#                     print('stop order already placed')
#                 except Exception as e:
#                     print(e)
#                     print('stop order cannot be placed')
#                     logger.info(f'Stop order cannot be placed for {ticker}')
    
#     def get_account_cash(self):
#         """Get available cash in account"""
#         return float(self.trading_client.get_account().cash)


# """
# Order execution handler for interacting with Alpaca broker
# """
# import pandas as pd
# from alpaca.trading.client import TradingClient
# from alpaca.trading.requests import (
#     MarketOrderRequest, 
#     StopLimitOrderRequest,
#     GetOrdersRequest
# )
# from alpaca.trading.enums import OrderSide, QueryOrderStatus, TimeInForce
# from ..config import API_KEY, SECRET_KEY, LIST_OF_TICKERS, STOP_PERC, normalize_symbol
# from ..logger import logger


# class OrderExecutor:
#     def __init__(self):
#         self.trading_client = TradingClient(API_KEY, SECRET_KEY, paper=True)
    
#     def get_open_position(self):
#         pos = self.trading_client.get_all_positions()
#         new_pos = [dict(elem) for elem in pos]
#         pos_df = pd.DataFrame(new_pos)
        
#         if pos_df.empty:
#             return pos_df
        
#         # Normalize tickers for matching
#         ticker_list = [normalize_symbol(i) for i in LIST_OF_TICKERS]
#         pos_df = pos_df[pos_df['symbol'].isin(ticker_list)]
#         return pos_df
    
#     def get_open_orders(self):
#         request_params = GetOrdersRequest(status=QueryOrderStatus.OPEN)
#         orders = self.trading_client.get_orders(filter=request_params)
#         new_order = [dict(elem) for elem in orders]
#         order_df = pd.DataFrame(new_order)
        
#         if not order_df.empty:
#             ticker_list = [normalize_symbol(i) for i in LIST_OF_TICKERS]
#             order_df = order_df[order_df['symbol'].isin(ticker_list)]
#         return order_df
    
#     def place_market_order(self, symbol, quantity, side):
#         """
#         Place a market order and auto-attach stop-loss
#         """
#         norm_symbol = normalize_symbol(symbol)

#         try:
#             market_order_data = MarketOrderRequest(
#                 symbol=norm_symbol,
#                 qty=quantity,
#                 side=side,
#                 time_in_force=TimeInForce.GTC
#             )
#             market_order = self.trading_client.submit_order(order_data=market_order_data)
#             logger.info(f"Order placed: {side} {quantity} {norm_symbol}")
#             print(market_order)
#             return market_order
#         except Exception as e:
#             logger.error(f"❌ Order failed for {norm_symbol}: {e}")
#             return None
    
#     def place_stop_order(self, symbol, stop_price, quantity, side):
#         """
#         Place a stop order to protect position
#         """
#         norm_symbol = normalize_symbol(symbol)
#         logger.info(f'Placing stop order for {quantity} of {norm_symbol} at {stop_price}')

#         req = StopLimitOrderRequest(
#             symbol=norm_symbol,
#             qty=quantity,
#             side=side,
#             time_in_force=TimeInForce.GTC,
#             limit_price=round(stop_price, 2),
#             stop_price=round(stop_price, 2)
#         )
#         res = self.trading_client.submit_order(req)
#         return res
    
#     def check_and_place_stop_orders(self, pos_df, order_df):
#         """
#         Ensure stop orders exist for each open position
#         """
#         if not pos_df.empty:
#             for ticker in LIST_OF_TICKERS:
#                 norm_symbol = normalize_symbol(ticker)
#                 try:
#                     pos = self.trading_client.get_open_position(norm_symbol)
#                     buy_price = float(pos.avg_entry_price)
#                     quantity = abs(round(float(pos.qty), 2))
#                     side = pos.side

#                     if side == "long":
#                         exit_side = OrderSide.SELL
#                         stop_price = buy_price * (1 - STOP_PERC / 100)
#                     else:
#                         exit_side = OrderSide.BUY
#                         stop_price = buy_price * (1 + STOP_PERC / 100)
                    
#                     if order_df.empty or (norm_symbol not in order_df['symbol'].to_list()):
#                         self.place_stop_order(norm_symbol, stop_price, quantity, exit_side)
#                 except Exception as e:
#                     logger.info(f'Stop order cannot be placed for {ticker}: {e}')




"""
Order execution module: handles placing, closing, and managing orders
"""
import pandas as pd
import logging
from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.trading.requests import (
    MarketOrderRequest,
    StopLimitOrderRequest,
    GetOrdersRequest
)


class OrderExecutor:
    def __init__(self, api_key, secret_key, paper=True):
        """
        Initialize trading client
        """
        self.client = TradingClient(api_key, secret_key, paper=paper)
        self.logger = logging.getLogger(__name__)

    def get_account_cash(self):
        """Fetch available cash balance from the trading account"""
        try:
            account = self.client.get_account()
            cash = float(account.cash)
            self.logger.debug(f"[OrderExecutor] Account cash available: {cash}")
            return cash
        except Exception as e:
            self.logger.error(f"[OrderExecutor] Failed to fetch account cash: {e}")
            return 0.0

    def place_market_order(self, symbol, qty, side: OrderSide):
        """Place a market order"""
        try:
            order_data = MarketOrderRequest(
                symbol=symbol,
                qty=qty,
                side=side,
                time_in_force=TimeInForce.GTC
            )
            order = self.client.submit_order(order_data=order_data)
            self.logger.info(f"[OrderExecutor] Market order placed: {side} {qty} {symbol}")
            return order
        except Exception as e:
            self.logger.error(f"[OrderExecutor] Market order failed: {e}")
            return None

    def place_stop_order(self, symbol, stop_price, qty, side: OrderSide):
        """Place a stop-limit order"""
        try:
            order_data = StopLimitOrderRequest(
                symbol=symbol,
                qty=qty,
                side=side,
                time_in_force=TimeInForce.GTC,
                stop_price=round(stop_price, 2),
                limit_price=round(stop_price, 2)
            )
            order = self.client.submit_order(order_data=order_data)
            self.logger.info(f"[OrderExecutor] Stop order placed: {side} {qty} {symbol} @ {stop_price}")
            return order
        except Exception as e:
            self.logger.error(f"[OrderExecutor] Stop order failed: {e}")
            return None

    def close_order(self, symbol):
        """Cancel all open orders for a given symbol"""
        try:
            req = GetOrdersRequest(status="open")
            orders = self.client.get_orders(filter=req)
            for order in orders:
                if order.symbol == symbol:
                    self.client.cancel_order_by_id(order.id)
                    self.logger.info(f"[OrderExecutor] Cancelled order {order.id} for {symbol}")
        except Exception as e:
            self.logger.error(f"[OrderExecutor] Failed to cancel orders for {symbol}: {e}")

    def close_position(self, symbol):
        """Close an open position for a given symbol"""
        try:
            pos = self.client.get_open_position(symbol)
            qty = float(pos.qty)
            exit_price = float(pos.current_price)
            self.client.close_position(symbol)
            self.logger.info(f"[OrderExecutor] Closed position {symbol}: {qty} @ {exit_price}")
            return True, qty, exit_price
        except Exception as e:
            self.logger.error(f"[OrderExecutor] Failed to close position {symbol}: {e}")
            return False, 0, 0.0

    def get_open_orders(self):
        """Get all open orders as DataFrame"""
        try:
            req = GetOrdersRequest(status="open")
            orders = self.client.get_orders(filter=req)
            df = pd.DataFrame([o.__dict__ for o in orders])
            return df
        except Exception as e:
            self.logger.error(f"[OrderExecutor] Failed to fetch open orders: {e}")
            return pd.DataFrame()

    def get_open_position(self, symbol=None):
        """
        Get open positions, optionally filtered by symbol
        Returns DataFrame
        """
        try:
            if symbol:
                pos = self.client.get_open_position(symbol)
                return pd.DataFrame([{
                    "symbol": pos.symbol,
                    "qty": float(pos.qty),
                    "avg_entry": float(pos.avg_entry_price),
                    "current_price": float(pos.current_price),
                    "market_value": float(pos.market_value),
                    "unrealized_pl": float(pos.unrealized_pl)
                }])

            positions = self.client.get_all_positions()
            data = [{
                "symbol": p.symbol,
                "qty": float(p.qty),
                "avg_entry": float(p.avg_entry_price),
                "current_price": float(p.current_price),
                "market_value": float(p.market_value),
                "unrealized_pl": float(p.unrealized_pl)
            } for p in positions]
            return pd.DataFrame(data)
        except Exception as e:
            self.logger.error(f"[OrderExecutor] Failed to fetch positions: {e}")
            return pd.DataFrame(columns=["symbol", "qty", "avg_entry", "current_price", "market_value", "unrealized_pl"])
