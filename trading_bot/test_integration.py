#!/usr/bin/env python3
"""
Test script for Drift Protocol Trading Bot
Run this to verify all components work correctly before trading
"""

import asyncio
import sys
import os
from pathlib import Path

# Add the parent directory to Python path so we can import our modules
sys.path.insert(0, str(Path(__file__).parent))

from trading_bot.config import SOLANA_RPC_URL, DRIFT_ENV, PRIVATE_KEY
from trading_bot.logger import setup_logger
from trading_bot.data.data_handler import DriftDataHandler
from trading_bot.broker.execution import DriftOrderExecutor
from trading_bot.risk.risk_manager import DriftRiskManager
from trading_bot.portfolio.portfolio_tracker import DriftPortfolioTracker


async def test_configuration():
    """Test configuration settings"""
    print("🔧 Testing Configuration...")
    
    print(f"   RPC URL: {SOLANA_RPC_URL}")
    print(f"   Environment: {DRIFT_ENV}")
    print(f"   Private Key: {'✅ Set' if PRIVATE_KEY else '❌ Missing'}")
    
    if not PRIVATE_KEY:
        print("   ⚠️  Please set PRIVATE_KEY in .env file")
        return False
    
    print("   ✅ Configuration OK")
    return True


async def test_data_handler():
    """Test data handler functionality"""
    print("\n📊 Testing Data Handler...")
    
    try:
        data_handler = DriftDataHandler()
        await data_handler.initialize()
        
        # Test getting current price
        current_price = await data_handler.get_current_price("SOL-PERP")
        print(f"   Current SOL-PERP price: ${current_price:.4f}")
        
        # Test historical data generation
        hist_data = await data_handler.get_historical_crypto_data("SOL-PERP", 7, "Hour")
        print(f"   Generated {len(hist_data)} historical bars")
        
        await data_handler.cleanup()
        print("   ✅ Data Handler OK")
        return True
        
    except Exception as e:
        print(f"   ❌ Data Handler Error: {e}")
        return False


async def test_order_executor():
    """Test order executor initialization"""
    print("\n💼 Testing Order Executor...")
    
    try:
        executor = DriftOrderExecutor(PRIVATE_KEY)
        await executor.initialize()
        
        # Test getting account balance
        balance = await executor.get_account_balance()
        print(f"   Account Balance: ${balance:.2f} USDC")
        
        # Test getting positions
        positions = await executor.get_open_position()
        print(f"   Open Positions: {len(positions)}")
        
        # Test getting orders
        orders = await executor.get_open_orders()
        print(f"   Open Orders: {len(orders)}")
        
        await executor.cleanup()
        print("   ✅ Order Executor OK")
        return True
        
    except Exception as e:
        print(f"   ❌ Order Executor Error: {e}")
        return False


def test_risk_manager():
    """Test risk manager functionality"""
    print("\n🛡️  Testing Risk Manager...")
    
    try:
        risk_manager = DriftRiskManager()
        
        # Test position sizing
        test_balance = 1000.0
        test_price = 100.0
        position_size = risk_manager.calculate_position_size(test_balance, test_price)
        print(f"   Position Size: {position_size:.6f} for ${test_balance} balance at ${test_price}")
        
        # Test stop loss calculation
        stop_price = risk_manager.calculate_stop_loss(test_price, "long")
        print(f"   Stop Loss: ${stop_price:.4f} for long at ${test_price}")
        
        # Test risk metrics
        metrics = risk_manager.get_risk_metrics()
        print(f"   Risk Config: {metrics}")
        
        print("   ✅ Risk Manager OK")
        return True
        
    except Exception as e:
        print(f"   ❌ Risk Manager Error: {e}")
        return False


def test_portfolio_tracker():
    """Test portfolio tracker functionality"""
    print("\n📈 Testing Portfolio Tracker...")
    
    try:
        tracker = DriftPortfolioTracker()
        
        # Test recording a sample trade
        tracker.record_trade(
            symbol="SOL-PERP",
            side="buy",
            price=100.0,
            quantity=0.1,
            tx_signature="test_tx_12345"
        )
        
        # Test getting trades
        trades = tracker.get_trades()
        print(f"   Total Trades: {len(trades)}")
        
        # Test P&L calculation
        pnl_stats = tracker.calculate_pnl()
        print(f"   P&L Stats: {pnl_stats}")
        
        print("   ✅ Portfolio Tracker OK")
        return True
        
    except Exception as e:
        print(f"   ❌ Portfolio Tracker Error: {e}")
        return False


async def run_integration_test():
    """Run comprehensive integration test"""
    print("🧪 Running Drift Protocol Trading Bot Integration Test")
    print("=" * 60)
    
    # Setup logger
    logger = setup_logger("test_bot")
    
    test_results = []
    
    # Run individual tests
    test_results.append(await test_configuration())
    test_results.append(await test_data_handler())
    test_results.append(await test_order_executor())
    test_results.append(test_risk_manager())
    test_results.append(test_portfolio_tracker())
    
    # Summary
    print("\n" + "=" * 60)
    print("📋 Test Summary")
    print("=" * 60)
    
    passed = sum(test_results)
    total = len(test_results)
    
    print(f"Tests Passed: {passed}/{total}")
    
    if passed == total:
        print("🎉 All tests passed! Bot is ready to run.")
        print("\nNext steps:")
        print("1. Make sure you have testnet SOL in your wallet")
        print("2. Review configuration in config.py")
        print("3. Run the bot: python -m dex_trading_bot.main")
        return True
    else:
        print("❌ Some tests failed. Please check the errors above.")
        print("\nTroubleshooting:")
        print("1. Verify .env file configuration")
        print("2. Check internet connection")
        print("3. Ensure RPC endpoint is accessible")
        print("4. Verify private key format")
        return False


if __name__ == "__main__":
    try:
        success = asyncio.run(run_integration_test())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n💥 Fatal test error: {e}")
        sys.exit(1)