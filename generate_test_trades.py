#!/usr/bin/env python3
"""
Test Data Generator for Drift Trading Bot Dashboard
Generates realistic trade data with proper fees, P&L, and account equity
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '.'))

from trading_bot.config import TRADES_FILE, TIMEZONE
from trading_bot.portfolio.portfolio_tracker import DriftPortfolioTracker
from trading_bot.logger import logger

def generate_realistic_trades(num_trades: int = 20, initial_balance: float = 10000.0):
    """
    Generate realistic BTC-PERP trading data with proper P&L, fees, and metrics
    
    Args:
        num_trades: Number of trades to generate (pairs of entry/exit)
        initial_balance: Starting account balance
    """
    logger.info(f"🎯 Generating {num_trades} realistic BTC-PERP trades...")
    
    # Initialize portfolio tracker
    portfolio = DriftPortfolioTracker()
    
    # BTC price range (realistic for recent data)
    btc_prices = np.array([
        42500, 42800, 42300, 42900, 43100, 43400, 42700, 43200, 
        42900, 43500, 43800, 43600, 44000, 43900, 43700, 44200,
        44400, 44100, 44500, 44800, 44600, 45000
    ])
    
    # Simulate trades
    current_time = datetime.now(TIMEZONE) - timedelta(days=5)
    current_balance = initial_balance
    trades_data = []
    
    for i in range(num_trades):
        # Random parameters for each trade
        is_long = np.random.choice([True, False])
        entry_price = btc_prices[i % len(btc_prices)] + np.random.uniform(-200, 200)
        
        # Position size: 0.05 - 0.15 BTC (realistic for account size)
        position_size = np.random.uniform(0.05, 0.15)
        
        # P&L outcome: 60% winning, 40% losing
        is_winning = np.random.random() < 0.60
        
        if is_winning:
            # Winning trade: 1-5% profit on notional
            profit_pct = np.random.uniform(0.01, 0.05)
            close_price = entry_price * (1 + profit_pct) if is_long else entry_price * (1 - profit_pct)
        else:
            # Losing trade: -0.5% to -3% loss on notional
            loss_pct = np.random.uniform(-0.03, -0.005)
            close_price = entry_price * (1 + loss_pct) if is_long else entry_price * (1 - loss_pct)
        
        # Calculate P&L (before fees)
        if is_long:
            gross_pnl = position_size * (close_price - entry_price)
        else:
            gross_pnl = position_size * (entry_price - close_price)
        
        # Drift Protocol fees (0.035% base tier - verified per https://docs.drift.trade/trading/trading-fees)
        entry_notional = entry_price * position_size
        exit_notional = close_price * position_size
        entry_fee = entry_notional * 0.00035  # 0.035% taker fee (Drift Tier 1)
        exit_fee = exit_notional * 0.00035    # 0.035% taker fee (Drift Tier 1)
        
        # Funding costs (hourly, ~ 0.01-0.03% per 8 hours held)
        hold_hours = np.random.uniform(4, 48)
        funding_rate = 0.0001  # 0.01% per 8 hours
        funding_paid = entry_notional * funding_rate * (hold_hours / 8)
        
        # Net P&L
        total_costs = entry_fee + exit_fee + funding_paid
        net_pnl = gross_pnl - total_costs
        
        # Update balance
        current_balance += net_pnl
        
        # Entry trade timestamp
        entry_time = current_time + timedelta(hours=i*2)
        exit_time = entry_time + timedelta(hours=hold_hours)
        
        # Record entry trade
        logger.info(f"\n📍 Trade #{i+1}: {'LONG' if is_long else 'SHORT'}")
        logger.info(f"   Entry: {position_size:.4f} BTC @ ${entry_price:,.2f}")
        logger.info(f"   Exit:  {position_size:.4f} BTC @ ${close_price:,.2f}")
        logger.info(f"   Gross P&L: ${gross_pnl:,.2f} | Fees: ${total_costs:,.4f} | Net: ${net_pnl:,.2f}")
        
        # Entry trade
        entry_tx = f"{'5' if is_long else '3'}{i:012d}{'L' if is_long else 'S'}ENTRY{np.random.randint(10000, 99999)}"
        portfolio.record_trade(
            symbol="BTC-PERP",
            side="BUY" if is_long else "SELL",
            price=entry_price,
            quantity=position_size,
            sl=entry_price * 0.95 if is_long else entry_price * 1.05,  # 5% SL
            tp=entry_price * 1.10 if is_long else entry_price * 0.90,  # 10% TP
            tx_signature=entry_tx,
            market_index=1,
            market_type="perp",
            order_type="market",
            fee=entry_fee,
            slippage_bps=5.0,
            pnl=0.0,  # No P&L on entry
            unrealized_pnl=gross_pnl,
            status="OPEN",
            duration_seconds=hold_hours * 3600,
            account_equity=current_balance - net_pnl,  # Balance before this trade's close
            leverage=2.0,
            sub_account_id=0,
            strategy_id="macd_btc_4h",
            signal_confidence=0.75,
            signal_type="momentum",
            slot=np.random.randint(100000000, 999999999),
            block_time=entry_time.isoformat(),
            oracle_price_at_entry=entry_price,
            execution_latency_ms=np.random.uniform(50, 500),
            bot_version="1.2.0",
            env="devnet",
            funding_paid=0.0,  # Funding on entry is 0
            cumulative_funding=0.0,
            entry_hold_minutes=0.0,
            taker_fee_rate=0.0005,
            maker_fee_rate=0.0002,
            net_pnl_after_fees=-entry_fee  # Entry only has entry fee
        )
        
        # Exit trade (CLOSE)
        exit_tx = f"{'4' if is_long else '2'}{i:012d}{'L' if is_long else 'S'}EXIT{np.random.randint(10000, 99999)}"
        portfolio.record_trade(
            symbol="BTC-PERP",
            side="CLOSE",
            price=close_price,
            quantity=position_size,
            sl=0.0,
            tp=0.0,
            tx_signature=exit_tx,
            market_index=1,
            market_type="perp",
            order_type="market",
            fee=exit_fee,
            slippage_bps=3.0,
            pnl=gross_pnl,  # Gross P&L
            unrealized_pnl=0.0,
            status="CLOSED",
            duration_seconds=hold_hours * 3600,
            account_equity=current_balance,  # Balance after trade
            leverage=2.0,
            sub_account_id=0,
            strategy_id="macd_btc_4h",
            signal_confidence=0.75,
            signal_type="momentum",
            slot=np.random.randint(100000000, 999999999),
            block_time=exit_time.isoformat(),
            oracle_price_at_entry=entry_price,
            execution_latency_ms=np.random.uniform(50, 500),
            bot_version="1.2.0",
            env="devnet",
            funding_paid=funding_paid,  # Funding paid during hold
            cumulative_funding=funding_paid,
            entry_hold_minutes=hold_hours * 60,
            taker_fee_rate=0.0005,
            maker_fee_rate=0.0002,
            net_pnl_after_fees=net_pnl  # Net P&L after all costs
        )
        
        trades_data.append({
            'trade_num': i + 1,
            'direction': 'LONG' if is_long else 'SHORT',
            'entry_price': entry_price,
            'exit_price': close_price,
            'quantity': position_size,
            'gross_pnl': gross_pnl,
            'fees': total_costs,
            'net_pnl': net_pnl,
            'balance_after': current_balance
        })
    
    # Save trades
    portfolio.save_trades()
    logger.info(f"\n✅ Successfully generated {num_trades} trades!")
    
    # Print summary
    logger.info("\n" + "="*80)
    logger.info("📊 TEST TRADES SUMMARY")
    logger.info("="*80)
    
    summary_df = pd.DataFrame(trades_data)
    
    total_gross = summary_df['gross_pnl'].sum()
    total_fees = summary_df['fees'].sum()
    total_net = summary_df['net_pnl'].sum()
    winning = (summary_df['net_pnl'] > 0).sum()
    losing = (summary_df['net_pnl'] < 0).sum()
    win_rate = (winning / len(summary_df) * 100) if len(summary_df) > 0 else 0
    
    logger.info(f"Total Trades: {len(summary_df)}")
    logger.info(f"Winning: {winning} | Losing: {losing} | Win Rate: {win_rate:.1f}%")
    logger.info(f"")
    logger.info(f"Gross P&L:    ${total_gross:>12,.2f}")
    logger.info(f"Total Fees:   ${total_fees:>12,.2f}")
    logger.info(f"Net P&L:      ${total_net:>12,.2f}")
    logger.info(f"")
    logger.info(f"Starting Balance: ${initial_balance:,.2f}")
    logger.info(f"Final Balance:    ${current_balance:,.2f}")
    logger.info(f"Return %:         {((current_balance - initial_balance) / initial_balance * 100):.2f}%")
    logger.info("="*80)
    
    # Show last 5 trades
    logger.info("\n📋 Last 5 Trades:")
    display_df = summary_df.tail(5)[['trade_num', 'direction', 'entry_price', 'exit_price', 'quantity', 'net_pnl', 'balance_after']]
    for idx, row in display_df.iterrows():
        logger.info(f"  {int(row['trade_num']):2d}. {row['direction']:5s} {row['quantity']:.4f} BTC @ ${row['entry_price']:>10,.2f} → ${row['exit_price']:>10,.2f} | Net: ${row['net_pnl']:>10,.2f} | Balance: ${row['balance_after']:>12,.2f}")
    
    logger.info("\n✅ Data saved to trades.csv - dashboard will now display all metrics!")
    return current_balance

if __name__ == "__main__":
    # Generate test trades
    final_balance = generate_realistic_trades(num_trades=20, initial_balance=10000.0)
    logger.info(f"\n🎉 Test data generation complete! Final balance: ${final_balance:,.2f}")
