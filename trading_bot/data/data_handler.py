
"""
Data handler for fetching historical crypto data from Drift Protocol and Solana
"""
import asyncio
import os
from datetime import datetime, timedelta
from pathlib import Path
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

# Map of symbol names to CoinGecko coin IDs
_COINGECKO_ID_MAP = {
    "BTC-PERP": "bitcoin",
    "ETH-PERP": "ethereum",
    "SOL-PERP": "solana",
}

# Map timeframe strings to (label, minutes_per_bar)
_TIMEFRAME_MAP = {
    "1m":  ("1m", 1),
    "5m":  ("5m", 5),
    "15m": ("15m", 15),
    "1h":  ("1h", 60),
    "4h":  ("4h", 240),
    "1d":  ("1d", 1440),
    # aliases
    "minute": ("1m", 1),
    "min":    ("1m", 1),
    "hour":   ("1h", 60),
    "h":      ("1h", 60),
    "day":    ("1d", 1440),
    "d":      ("1d", 1440),
}


class DriftDataHandler:
    def __init__(self):
        """Initialize the Drift data handler"""
        self.connection = None
        self.drift_client: Optional[DriftClient] = None
        self.data_cache = {}  # Cache for historical data
        self._initialized = False
        self._init_retries = 3  # Number of retry attempts per RPC
        
    async def initialize(self):
        """Initialize Drift client connection with RPC fallback logic.
        
        Only needed for oracle price lookups (get_current_price).
        Historical OHLCV data uses CoinGecko + local CSV and does NOT require this.
        """
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
    
    def _resolve_timeframe(self, time_frame_unit: str):
        """Resolve a timeframe string to (label, minutes_per_bar)."""
        key = time_frame_unit.lower().strip()
        if key in _TIMEFRAME_MAP:
            return _TIMEFRAME_MAP[key]
        # Default to 1h if unrecognised
        logger.warning(f"Unrecognised timeframe '{time_frame_unit}', defaulting to 1h")
        return ("1h", 60)

    def _csv_path(self, ticker: str, timeframe_label: str) -> Path:
        """Return the path to the local CSV cache for a symbol/timeframe."""
        project_root = Path(__file__).resolve().parents[2]  # up from data/ -> trading_bot/ -> project root
        safe_label = timeframe_label.replace("/", "").replace("\\", "")
        return project_root / "data" / f"{ticker}_{safe_label}.csv"

    def _load_local_csv(self, ticker: str, timeframe_label: str) -> Optional[pd.DataFrame]:
        """Load OHLCV data from a local CSV file if it exists."""
        csv_path = self._csv_path(ticker, timeframe_label)
        if not csv_path.exists():
            return None
        try:
            df = pd.read_csv(csv_path, parse_dates=["timestamp"])
            if df.empty:
                return None
            df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
            df = df.set_index("timestamp").sort_index()
            # Ensure required columns
            for col in ("open", "high", "low", "close", "volume"):
                if col not in df.columns:
                    logger.warning(f"Local CSV missing column '{col}', discarding")
                    return None
            logger.info(f"📂 Loaded {len(df)} bars from {csv_path.name}")
            return df
        except Exception as e:
            logger.warning(f"Failed to read local CSV {csv_path}: {e}")
            return None

    def _save_to_csv(self, df: pd.DataFrame, ticker: str, timeframe_label: str) -> None:
        """Persist OHLCV DataFrame to local CSV for future runs."""
        csv_path = self._csv_path(ticker, timeframe_label)
        try:
            csv_path.parent.mkdir(parents=True, exist_ok=True)
            out = df.copy()
            out.index.name = "timestamp"
            out.to_csv(csv_path)
            logger.info(f"💾 Saved {len(out)} bars to {csv_path.name}")
        except Exception as e:
            logger.warning(f"Failed to save CSV: {e}")

    async def _fetch_from_coingecko(self, ticker: str, days: int) -> Optional[pd.DataFrame]:
        """
        Fetch OHLC data from CoinGecko free API.
        Returns a DataFrame indexed by UTC timestamp with columns: open, high, low, close, volume.

        CoinGecko /coins/{id}/ohlc returns:
          - 4h candles when days = 3–30
          - daily candles when days > 30
        So we clamp days to 30 max for 4h resolution.
        """
        import httpx

        coin_id = _COINGECKO_ID_MAP.get(ticker)
        if coin_id is None:
            logger.warning(f"No CoinGecko mapping for {ticker}, cannot fetch live data")
            return None

        # Clamp to 30 days to get 4h candles (~180 bars)
        days_param = min(max(days, 1), 30)
        url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/ohlc"
        params = {"vs_currency": "usd", "days": str(days_param)}

        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(20.0)) as client:
                resp = await client.get(url, params=params)
                resp.raise_for_status()
                data = resp.json()
        except Exception as e:
            logger.warning(f"CoinGecko API request failed: {e}")
            return None

        if not data:
            return None

        rows = []
        for candle in data:
            # Each candle: [timestamp_ms, open, high, low, close]
            rows.append({
                "timestamp": pd.Timestamp(candle[0], unit="ms", tz="UTC"),
                "open": float(candle[1]),
                "high": float(candle[2]),
                "low": float(candle[3]),
                "close": float(candle[4]),
                "volume": 0.0,  # CoinGecko OHLC endpoint does not provide volume
            })

        df = pd.DataFrame(rows)
        df = df.set_index("timestamp").sort_index()
        df = df[~df.index.duplicated(keep="last")]
        logger.info(f"🌐 Fetched {len(df)} bars from CoinGecko for {ticker} (days={days_param})")
        return df

    async def get_historical_crypto_data(self, ticker: str, duration: int, time_frame_unit: str) -> pd.DataFrame:
        """
        Get historical OHLCV data for a cryptocurrency.

        Data source priority:
          1. CoinGecko free API (4h candles for up to 30 days)
          2. Local CSV cache (data/<SYMBOL>_<timeframe>.csv)
          3. Synthetic random data (last resort)

        Args:
            ticker: Symbol (e.g., "BTC-PERP")
            duration: Number of calendar days of history to fetch
            time_frame_unit: Timeframe string – "4h", "1h", "Hour", "Day", etc.

        Returns:
            DataFrame with OHLCV data and technical indicators
        """
        timeframe_label, minutes_per_bar = self._resolve_timeframe(time_frame_unit)
        bars_needed = max(1, (duration * 24 * 60) // minutes_per_bar)

        cache_key = f"{ticker}_{duration}_{time_frame_unit}"

        # --- 1. Primary: Fetch from CoinGecko API ---
        df = None
        try:
            df = await self._fetch_from_coingecko(ticker, duration)
            if df is not None and not df.empty:
                # Save to CSV as cache for future cold starts
                self._save_to_csv(df, ticker, timeframe_label)
        except Exception as e:
            logger.warning(f"Could not fetch from CoinGecko: {e}")

        # --- 2. Fallback: local CSV cache (only if CoinGecko failed) ---
        if df is None or df.empty:
            logger.info("CoinGecko unavailable, falling back to local CSV cache")
            df = self._load_local_csv(ticker, timeframe_label)

        # --- 3. Last resort: synthetic data ---
        if df is None or df.empty:
            logger.warning(f"⚠️ No real data available for {ticker}, using synthetic data")
            # Try to get price from Drift oracle, but don't fail if unavailable
            current_price = 0.0
            try:
                current_price = await self.get_current_price(ticker)
            except Exception as e:
                logger.warning(f"Could not get oracle price for synthetic data: {e}")
            if current_price == 0:
                current_price = 100.0
            df = self._generate_synthetic_ohlcv(current_price, bars_needed)

        # Trim to requested duration
        if len(df) > bars_needed:
            df = df.iloc[-bars_needed:]

        # Add technical indicators
        from ..indicators.indicators import IndicatorCalculator
        indicator_calc = IndicatorCalculator()
        df = indicator_calc.add_indicators(df)

        self.data_cache[cache_key] = df
        logger.info(f"📊 Returning {len(df)} bars for {ticker} ({timeframe_label})")
        return df

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
        """
        if timeframe_minutes <= 1:
            tfu = "1m"
        elif timeframe_minutes <= 5:
            tfu = "5m"
        elif timeframe_minutes <= 15:
            tfu = "15m"
        elif timeframe_minutes <= 60:
            tfu = "1h"
        elif timeframe_minutes <= 240:
            tfu = "4h"
        else:
            tfu = "1d"
        return await self.get_historical_crypto_data(symbol, periods, tfu)


# Backwards compatibility alias
DataHandler = DriftDataHandler
