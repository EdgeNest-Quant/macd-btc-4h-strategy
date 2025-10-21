import pandas as pd
from datetime import datetime, timedelta
import pytz
import asyncio
from solders.keypair import Keypair
from anchorpy import Provider, Wallet
from solana.rpc.async_api import AsyncClient
from driftpy.drift_client import DriftClient
from driftpy.account_subscription_config import AccountSubscriptionConfig
import os
import sys

# Import config
import config

class ExternalPositionDetector:
    def __init__(self):
        self.drift_client = None
        self.wallet_keypair = None
        
    async def initialize(self):
        """Initialize Drift client"""
        print("🔌 Connecting to Drift Protocol...")
        
        # Get configuration from config.py
        private_key = config.PRIVATE_KEY
        rpc_url = config.SOLANA_RPC_URL
        env = config.DRIFT_ENV
        
        if not private_key:
            raise ValueError("PRIVATE_KEY not set in environment or .env file")
        
        # Load wallet
        self.wallet_keypair = Keypair.from_base58_string(private_key)
        wallet = Wallet(self.wallet_keypair)
        
        # Create connection
        connection = AsyncClient(rpc_url)
        provider = Provider(connection, wallet)
        
        # Create Drift client
        self.drift_client = DriftClient(
            connection,
            wallet,
            env,
            account_subscription=AccountSubscriptionConfig("cached")
        )
        
        await self.drift_client.subscribe()
        print(f"✅ Connected! Wallet: {self.wallet_keypair.pubkey()}")
        
    async def get_all_positions_from_drift(self):
        """Fetch ALL positions from Drift (including external ones)"""
        try:
            user = self.drift_client.get_user()
            positions = user.get_user_account().perp_positions
            
            active_positions = []
            for pos in positions:
                if pos.base_asset_amount != 0:  # Position is open
                    # Don't await - get_perp_market_account is synchronous
                    market = self.drift_client.get_perp_market_account(pos.market_index)
                    
                    # Get position details - FIX: Use correct precision
                    # base_asset_amount is in BASE_PRECISION (1e9)
                    # quote_asset_amount is in QUOTE_PRECISION (1e6)
                    size = abs(pos.base_asset_amount) / 1e9  # Convert from base units
                    
                    # Calculate entry price correctly
                    if pos.base_asset_amount != 0:
                        # Entry price = total quote / total base (both in their native precisions)
                        entry_price = abs(pos.quote_asset_amount / pos.base_asset_amount) * 1e3  # Adjust for precision difference
                    else:
                        entry_price = 0
                    
                    side = "LONG" if pos.base_asset_amount > 0 else "SHORT"
                    
                    # Decode market name - handle ListContainer (array of bytes)
                    if isinstance(market.name, str):
                        market_name = market.name
                    elif isinstance(market.name, bytes):
                        market_name = market.name.decode('utf-8').strip('\x00')
                    else:
                        # It's a ListContainer - convert to bytes first
                        market_name = bytes(market.name).decode('utf-8').strip('\x00')
                    
                    active_positions.append({
                        'market_index': pos.market_index,
                        'symbol': market_name,
                        'side': side,
                        'size': size,
                        'entry_price': entry_price,
                        'unrealized_pnl': pos.quote_asset_amount / 1e6,
                        'open_orders': pos.open_orders,
                        'last_cumulative_funding': pos.last_cumulative_funding_rate,
                    })
                    
                    print(f"   Found position: {market_name} {side} {size:.6f} @ ${entry_price:.2f}")
            
            return active_positions
        except Exception as e:
            print(f"❌ Error fetching positions: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    async def detect_external_positions(self):
        """Compare Drift positions with [trades.csv](http://_vscodecontentref_/0) to find external ones"""
        # Load existing trades - go up one directory to find [trades.csv](http://_vscodecontentref_/1)
        csv_path = os.path.join(os.path.dirname(__file__), '..', 'trades.csv')
        df = pd.read_csv(csv_path)
        df['timestamp'] = pd.to_datetime(df['timestamp'], format='mixed')
        
        # Get current open positions from [trades.csv](http://_vscodecontentref_/2) (bot's view)
        bot_open_positions = []
        
        # FIX: Normalize symbol names by stripping whitespace
        df['symbol'] = df['symbol'].str.strip()
        
        for symbol in df['symbol'].unique():
            if pd.isna(symbol):
                continue
                
            symbol_trades = df[df['symbol'] == symbol].sort_values('timestamp')
            
            # Calculate net position from bot trades
            net_position = 0
            for _, trade in symbol_trades.iterrows():
                if trade['side'] == 'BUY':
                    net_position += trade['quantity']
                elif trade['side'] == 'SELL':
                    net_position -= trade['quantity']
                elif trade['side'] == 'CLOSE':
                    net_position = 0
            
            if abs(net_position) > 0.0001:  # Position still open
                bot_open_positions.append({
                    'symbol': symbol,
                    'net_position': net_position
                })
                print(f"   Bot tracking: {symbol} = {net_position:.6f}")
        
        # Get actual positions from Drift
        drift_positions = await self.get_all_positions_from_drift()
        
        print(f"\n📊 Analysis:")
        print(f"   - Bot tracked positions: {len(bot_open_positions)}")
        print(f"   - Drift actual positions: {len(drift_positions)}")
        
        # Find external positions
        external_positions = []
        for drift_pos in drift_positions:
            symbol = drift_pos['symbol'].strip()  # Normalize symbol name
            drift_size = drift_pos['size'] if drift_pos['side'] == 'LONG' else -drift_pos['size']
            
            # Check if this position is tracked by bot
            bot_pos = next((p for p in bot_open_positions if p['symbol'] == symbol), None)
            bot_size = bot_pos['net_position'] if bot_pos else 0
            
            print(f"\n   {symbol}:")
            print(f"      Drift: {drift_size:.6f}")
            print(f"      Bot:   {bot_size:.6f}")
            print(f"      Diff:  {(drift_size - bot_size):.6f}")
            
            # If sizes don't match, there's an external position
            size_diff = drift_size - bot_size
            if abs(size_diff) > 0.0001:
                external_positions.append({
                    'symbol': symbol,
                    'external_size': size_diff,
                    'external_side': 'BUY' if size_diff > 0 else 'SELL',
                    'drift_total': drift_size,
                    'bot_tracked': bot_size,
                    'entry_price': drift_pos['entry_price'],
                    'unrealized_pnl': drift_pos['unrealized_pnl']
                })
        
        return external_positions
    
    async def add_external_positions_to_csv(self, external_positions):
        """Add external positions to trades.csv"""
        if not external_positions:
            print("\n✅ No external positions detected!")
            return
        
        print(f"\n⚠️  Found {len(external_positions)} external position(s):")
        
        # Load existing trades
        csv_path = os.path.join(os.path.dirname(__file__), '..', 'trades.csv')
        df = pd.read_csv(csv_path)
        
        # Create new rows for external positions
        new_rows = []
        for ext_pos in external_positions:
            print(f"\n   Symbol: {ext_pos['symbol']}")
            print(f"   Size: {ext_pos['external_size']:.6f}")
            print(f"   Side: {ext_pos['external_side']}")
            print(f"   Entry Price: ${ext_pos['entry_price']:.2f}")
            print(f"   Unrealized P&L: ${ext_pos['unrealized_pnl']:.2f}")
            
            # Create trade record
            new_row = {
                'timestamp': datetime.now(pytz.UTC).isoformat(),
                'symbol': ext_pos['symbol'],
                'market_index': 1,  # BTC-PERP
                'market_type': 'perp',
                'side': ext_pos['external_side'],
                'order_type': 'EXTERNAL',
                'price': ext_pos['entry_price'],
                'quantity': abs(ext_pos['external_size']),
                'fee': 0.0,
                'slippage_bps': 0.0,
                'sl': 0.0,
                'tp': 0.0,
                'pnl': 0.0,
                'unrealized_pnl': ext_pos['unrealized_pnl'],
                'status': 'OPEN',
                'duration_seconds': 0,
                'account_equity': 0.0,
                'leverage': 0.0,
                'sub_account_id': 0,
                'strategy_id': 'EXTERNAL',
                'signal_confidence': 0.0,
                'signal_type': 'EXTERNAL',
                'tx_signature': 'EXTERNAL_POSITION_DETECTED',
                'slot': 0,
                'block_time': '',
                'oracle_price_at_entry': ext_pos['entry_price'],
                'execution_latency_ms': 0,
                'bot_version': 'v1.0',
                'env': config.DRIFT_ENV
            }
            new_rows.append(new_row)
        
        # Append to CSV
        if new_rows:
            new_df = pd.DataFrame(new_rows)
            df = pd.concat([df, new_df], ignore_index=True)
            df.to_csv(csv_path, index=False)
            print(f"\n✅ Added {len(new_rows)} external position(s) to trades.csv")
    
    async def close(self):
        """Cleanup"""
        if self.drift_client:
            await self.drift_client.unsubscribe()

async def main():
    print("="*60)
    print("🔍 EXTERNAL POSITION DETECTOR & LOGGER")
    print("="*60)
    
    detector = ExternalPositionDetector()
    
    try:
        await detector.initialize()
        external_positions = await detector.detect_external_positions()
        await detector.add_external_positions_to_csv(external_positions)
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await detector.close()
    
    print("\n" + "="*60)
    print("✅ Detection complete!")
    print("="*60)

if __name__ == "__main__":
    asyncio.run(main())