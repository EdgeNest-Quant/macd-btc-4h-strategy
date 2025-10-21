import os
import asyncio
from solders.keypair import Keypair
from driftpy.drift_client import DriftClient
from solana.rpc.async_api import AsyncClient
from dotenv import load_dotenv

load_dotenv()

async def main():
    rpc_url = os.getenv("SOLANA_RPC_URL", "https://api.devnet.solana.com")
    kp = Keypair.from_base58_string(os.getenv("PRIVATE_KEY"))

    # Connect to Solana Devnet
    connection = AsyncClient(rpc_url)
    client = DriftClient(connection, kp, "devnet")

    # Load Drift user accounts
    await client.subscribe()

    # Get your Drift user data
    user = client.get_user()

    # ✅ These are synchronous (don't use await)
    collateral = user.get_total_collateral()
    free_collateral = user.get_free_collateral()
    net_usd_value = user.get_net_usd_value()

    print("\n✅ Drift Account Loaded Successfully")
    print(f"💰 Total Collateral: {collateral / 1e6:.2f} USDC")
    print(f"🟢 Free Collateral: {free_collateral / 1e6:.2f} USDC")
    print(f"💎 Net USD Value: {net_usd_value / 1e6:.2f} USD")

    # Get spot positions
    print("\n📊 SPOT POSITIONS:")
    has_spot_positions = False
    
    # From the partial output, we know SOL is in market index 1
    # Let's check all possible market indices to find positions
    for market_index in range(20):  # Check first 20 spot markets
        try:
            position = user.get_spot_position(market_index)
            if position and position.scaled_balance != 0:  # Only show non-zero positions
                has_spot_positions = True
                
                # Try to determine token symbol and correct decimals
                if market_index == 0:
                    symbol = "USDC"
                    balance = position.scaled_balance / 1e6  # USDC has 6 decimals
                elif market_index == 1:
                    symbol = "SOL"
                    # The partial output showed raw balance: 92413 which suggests it's not in standard SOL decimals
                    # Let's try different decimal interpretations
                    raw_balance = position.scaled_balance
                    print(f"  {symbol}: {raw_balance / 1e9:.9f} (Standard 9 decimals)")
                    print(f"  {symbol}: {raw_balance / 1e6:.6f} (6 decimals)")
                    print(f"  {symbol}: {raw_balance / 1e3:.3f} (3 decimals)")
                    print(f"  {symbol}: {raw_balance:.0f} (Raw balance)")
                    continue
                elif market_index == 2:
                    symbol = "BTC"
                    balance = position.scaled_balance / 1e8  # BTC typically has 8 decimals
                elif market_index == 3:
                    symbol = "ETH"  
                    balance = position.scaled_balance / 1e18  # ETH has 18 decimals
                else:
                    symbol = f"TOKEN_{market_index}"
                    balance = position.scaled_balance / 1e9
                
                print(f"  {symbol}: {balance:.6f}")
        except Exception as e:
            # Skip if market doesn't exist or other error
            continue
    
    if not has_spot_positions:
        print("  No spot positions")

    # Get perp positions
    print("\n🚀 PERP POSITIONS:")
    has_perp_positions = False
    
    # Check common perp market indices
    for market_index in range(10):  # Check first 10 perp markets
        try:
            position = user.get_perp_position(market_index)
            if position and position.base_asset_amount != 0:  # Only show non-zero positions
                has_perp_positions = True
                base_amount = position.base_asset_amount / 1e9  # Adjust for decimals
                
                # Determine market symbol
                if market_index == 0:
                    symbol = "SOL-PERP"
                elif market_index == 1:
                    symbol = "BTC-PERP"
                elif market_index == 2:
                    symbol = "ETH-PERP"
                else:
                    symbol = f"PERP_{market_index}"
                
                direction = "LONG" if base_amount > 0 else "SHORT"
                print(f"  {symbol}: {abs(base_amount):.6f} ({direction})")
        except:
            # Skip if market doesn't exist or other error
            continue
    
    if not has_perp_positions:
        print("  No active perp positions")

    # Get open orders - simplified approach
    print("\n📋 OPEN ORDERS:")
    try:
        # Try to get orders by checking user account data directly
        user_account = user.user_account
        orders = user_account.orders if hasattr(user_account, 'orders') else []
        active_orders = [order for order in orders if hasattr(order, 'status') and order.status == 0]
        
        if active_orders:
            for order in active_orders:
                print(f"  Order found: {order}")
        else:
            print("  No open orders")
    except Exception as e:
        print("  No open orders")

    print("\n" + "="*50)
    print("📊 BALANCE ANALYSIS:")
    print(f"Script Net Value: ${net_usd_value / 1e6:.2f}")
    print(f"UI Net Value: $445.93 (from your screenshot)")
    print("")
    print("🔍 The difference might be due to:")
    print("1. SOL balance scaling issue (0.000092 vs 2.00036)")
    print("2. Different calculation methods between UI and API")
    print("3. Timestamp differences in price feeds")
    print("="*50)

    await connection.close()

if __name__ == "__main__":
    asyncio.run(main())