
"""
Data handler for fetching historical crypto data from Drift Protocol and Solana
"""
import asyncio
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from typing import Optional, Dict, Any
from ..config import RPC_ENDPOINTS, DRIFT_ENV, get_market_index_by_symbol, TIMEZONE
from ..logger import logger

try:
    from solana.rpc.async_api import AsyncClient
    from driftpy.drift_client import DriftClient
    from driftpy.account_subscription_config import AccountSubscriptionConfig
    from anchorpy import Wallet
    from solders.keypair import Keypair
except ImportError as e:
    logger.error(f"Failed to import Drift dependencies: {e}")
    logger.error("Please install requirements: pip install -r requirements.txt")
    raise


class DriftDataHandler:
    def __init__(self):
        """Initialize the Drift data handler"""
        self.connection = None
        self.drift_client: Optional[DriftClient] = None
        self.data_cache = {}  # Cache for historical data
        self._initialized = False
        self._init_retries = 3  # Number of retry attempts per RPC
        
    async def initialize(self):
        """Initialize Drift client connection with RPC fallback logic"""
        if self._initialized:
            return
        
        import httpx
        
        # Try each RPC endpoint in order
        for rpc_idx, rpc_url in enumerate(RPC_ENDPOINTS):
            logger.info(f"🔄 Trying RPC endpoint {rpc_idx + 1}/{len(RPC_ENDPOINTS)}: {rpc_url[:60]}...")
            
            # Retry each endpoint multiple times before moving to next
            for attempt in range(self._init_retries):
                try:
                    # Exponential timeout: 30s, 45s, 67s
                    timeout_seconds = 30.0 * (1.5 ** attempt)
                    logger.info(f"   Attempt {attempt + 1}/{self._init_retries} (timeout: {timeout_seconds:.0f}s)")
                    
                    # Create new connection with current RPC
                    self.connection = AsyncClient(
                        rpc_url,
                        timeout=httpx.Timeout(timeout_seconds, connect=10.0)
                    )
                    
                    # Create dummy wallet for read-only operations
                    dummy_keypair = Keypair()
                    wallet = Wallet(dummy_keypair)
                    
                    # Create Drift client with new connection
                    self.drift_client = DriftClient(
                        connection=self.connection,
                        wallet=wallet,
                        env=DRIFT_ENV,
                        account_subscription=AccountSubscriptionConfig("cached")
                    )
                    
                    # Subscribe with timeout
                    await asyncio.wait_for(
                        self.drift_client.subscribe(), 
                        timeout=timeout_seconds
                    )
                    
                    self._initialized = True
                    logger.info(f"✅ Successfully connected using RPC: {rpc_url[:60]}")
                    logger.info(f"✅ Drift data handler initialized for {DRIFT_ENV}")
                    return
                    
                except asyncio.TimeoutError:
                    logger.warning(f"   ⏱️  Subscription timed out after {timeout_seconds:.0f}s")
                    if attempt < self._init_retries - 1:
                        wait_time = 2 ** attempt  # 1s, 2s, 4s
                        logger.info(f"   Waiting {wait_time}s before retry...")
                        await asyncio.sleep(wait_time)
                    else:
                        logger.warning(f"   ❌ All attempts failed for this RPC endpoint")
                        
                except Exception as e:
                    logger.warning(f"   ⚠️  Error: {str(e)[:100]}")
                    if attempt < self._init_retries - 1:
                        wait_time = 2 ** attempt
                        logger.info(f"   Waiting {wait_time}s before retry...")
                        await asyncio.sleep(wait_time)
                    else:
                        logger.warning(f"   ❌ All attempts failed for this RPC endpoint")
        
        # If we get here, all RPCs failed
        logger.error(f"❌ Failed to connect to Drift using any of {len(RPC_ENDPOINTS)} RPC endpoints")
        raise Exception("All RPC endpoints failed after multiple retry attempts")
    
    async def get_current_price(self, symbol: str) -> float:
        """
        Get current price for a symbol from Drift oracle
        
        Args:
            symbol: Market symbol (e.g., "SOL-PERP")
            
        Returns:
            Current price as float
        """
        if not self._initialized:
            await self.initialize()
            
        try:
            market_index = get_market_index_by_symbol(symbol)
            
            if symbol.endswith("-PERP"):
                # Perpetual market
                oracle_data = self.drift_client.get_oracle_price_data_for_perp_market(market_index)
            else:
                # Spot market  
                oracle_data = self.drift_client.get_oracle_price_data_for_spot_market(market_index)
                
            if oracle_data:
                # Convert from Drift's price precision (1e6) to regular price
                return float(oracle_data.price) / 1e6
            else:
                logger.warning(f"No oracle data found for {symbol}")
                return 0.0
                
        except Exception as e:
            logger.error(f"Error getting current price for {symbol}: {e}")
            return 0.0
    
    def _generate_synthetic_ohlcv(self, current_price: float, duration_minutes: int) -> pd.DataFrame:
        """
        Generate synthetic OHLCV data for backtesting when historical data is not available
        This creates realistic price movements with some volatility
        """
        timestamps = []
        opens = []
        highs = []
        lows = []
        closes = []
        volumes = []
        
        # Start from current time and go back
        # Generate synthetic timestamps (recent historical data)
        end_time = datetime.now(TIMEZONE)
        
        current_close = current_price
        
        for i in range(duration_minutes):
            # Create consistent pandas Timestamp from datetime
            timestamp = pd.Timestamp(end_time) - pd.Timedelta(minutes=i)
            timestamps.append(timestamp)
            
            # Generate realistic OHLCV with some randomness
            # Random price movement between -2% to +2%
            price_change = np.random.uniform(-0.02, 0.02)
            new_close = current_close * (1 + price_change)
            
            # Generate OHLC based on close
            volatility = np.random.uniform(0.005, 0.02)  # 0.5% to 2% volatility
            high = new_close * (1 + volatility/2)
            low = new_close * (1 - volatility/2)
            open_price = current_close
            
            opens.append(open_price)
            highs.append(high)
            lows.append(low)
            closes.append(new_close)
            volumes.append(np.random.uniform(1000, 10000))  # Random volume
            
            current_close = new_close
        
        # Reverse to get chronological order
        timestamps.reverse()
        opens.reverse()
        highs.reverse()
        lows.reverse()
        closes.reverse()
        volumes.reverse()
        
        df = pd.DataFrame({
            'timestamp': timestamps,
            'open': opens,
            'high': highs,
            'low': lows,
            'close': closes,
            'volume': volumes
        })
        
        # Ensure proper datetime index with timezone info
        try:
            # Convert to datetime, handling both naive and timezone-aware timestamps
            if not df['timestamp'].empty:
                # Check if timestamps are already pandas Timestamps
                if isinstance(df['timestamp'].iloc[0], pd.Timestamp):
                    # Ensure timezone consistency
                    if df['timestamp'].iloc[0].tz is None:
                        df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)
                    else:
                        df['timestamp'] = df['timestamp'].dt.tz_convert('UTC')
                else:
                    df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)
                
                df = df.set_index('timestamp')
                # Ensure index is timezone-aware UTC
                if df.index.tz is None:
                    df.index = df.index.tz_localize('UTC')
                else:
                    df.index = df.index.tz_convert('UTC')
            return df
        except Exception as e:
            logger.error(f"Error processing DataFrame timestamps: {e}")
            # Fallback: create simple numeric index
            if 'timestamp' in df.columns:
                df = df.drop('timestamp', axis=1)
            return df
    
    async def get_historical_crypto_data(self, ticker: str, duration: int, time_frame_unit: str) -> pd.DataFrame:
        """
        Get historical data for a cryptocurrency pair
        
        Args:
            ticker: Symbol (e.g., "SOL-PERP")
            duration: Number of days/hours/minutes to fetch
            time_frame_unit: "Minute", "Hour", or "Day"
            
        Returns:
            DataFrame with OHLCV data and technical indicators
        """
        if not self._initialized:
            await self.initialize()
            
        cache_key = f"{ticker}_{duration}_{time_frame_unit}"
        
        try:
            # For now, we'll use synthetic data since Drift doesn't provide historical OHLCV
            # In a real implementation, you'd fetch from a historical data provider
            current_price = await self.get_current_price(ticker)
            
            if current_price == 0:
                logger.warning(f"Could not get current price for {ticker}, using default")
                current_price = 100.0  # Default price for testing
            
            # Generate duration based on time frame
            if time_frame_unit.lower() in ["minute", "min"]:
                duration_minutes = duration * 24 * 60  # days to minutes
            elif time_frame_unit.lower() in ["hour", "h"]:  
                duration_minutes = duration * 60  # hours to minutes
            else:  # day
                duration_minutes = duration * 24 * 60  # days to minutes
                
            # Limit to reasonable amount for performance
            duration_minutes = min(duration_minutes, 10000)
            
            df = self._generate_synthetic_ohlcv(current_price, duration_minutes)
            
            # Add technical indicators
            from ..indicators.indicators import IndicatorCalculator
            indicator_calc = IndicatorCalculator()
            df = indicator_calc.add_indicators(df)
            
            # Cache the result
            self.data_cache[cache_key] = df
            
            logger.debug(f"Generated {len(df)} bars for {ticker}")
            return df
            
        except Exception as e:
            logger.error(f"Error fetching historical data for {ticker}: {e}")
            # Return empty DataFrame with expected columns
            return pd.DataFrame(columns=['open', 'high', 'low', 'close', 'volume'])
    
    async def cleanup(self):
        """Clean up resources"""
        if self.drift_client and self._initialized:
            try:
                await self.drift_client.unsubscribe()
                logger.info("Drift data handler cleaned up")
            except Exception as e:
                logger.error(f"Error during cleanup: {e}")

        async def get_historical_data(self, symbol: str, periods: int = 1, timeframe_minutes: int = 1):
            """
            Compatibility wrapper for strategy code expecting get_historical_data.
            Calls get_historical_crypto_data with mapped arguments.
            Args:
                symbol: Market symbol (e.g., "BTC-PERP")
                periods: Number of periods (default 1)
                timeframe_minutes: Minutes per period (default 1)
            Returns:
                DataFrame with OHLCV and indicators
            """
            # Map periods and timeframe_minutes to duration and time_frame_unit
            duration = periods
            time_frame_unit = "Minute" if timeframe_minutes == 1 else "Hour" if timeframe_minutes == 60 else "Day"
            return await self.get_historical_crypto_data(symbol, duration, time_frame_unit)


# Backwards compatibility alias
DataHandler = DriftDataHandler
