"""
Migration script to upgrade trades.csv with enhanced metadata columns
"""

import pandas as pd
import os
from datetime import datetime

def migrate_trades_csv(old_file='trades.csv', new_file='trades_enhanced.csv'):
    """
    Migrate existing trades.csv to enhanced format with all new columns
    """
    print("🔄 Starting migration...")
    
    # Backup original
    backup_file = f"trades_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    if os.path.exists(old_file):
        os.system(f"cp {old_file} {backup_file}")
        print(f"✅ Backup created: {backup_file}")
    
    # Load existing trades
    df = pd.read_csv(old_file, parse_dates=['timestamp'])
    print(f"📊 Loaded {len(df)} existing trades")
    
    # Add new columns with default values
    new_columns = {
        # Order quality
        'order_type': 'market',
        'fee': 0.0,
        'slippage_bps': 0.0,
        
        # Trade outcome  
        'pnl': 0.0,
        'unrealized_pnl': 0.0,
        'status': 'UNKNOWN',  # Will need manual review
        'duration_seconds': 0.0,
        
        # Account context
        'account_equity': 0.0,
        'leverage': 1.0,
        'sub_account_id': 0,
        
        # Strategy metadata
        'strategy_id': 'legacy_macd',
        'signal_confidence': 0.0,
        'signal_type': 'momentum',
        
        # Blockchain data
        'slot': 0,
        'block_time': '',
        
        # Execution quality
        'oracle_price_at_entry': 0.0,
        'execution_latency_ms': 0.0,
        'bot_version': '1.0',
        'env': 'devnet'
    }
    
    # Add new columns
    for col, default_val in new_columns.items():
        if col not in df.columns:
            df[col] = default_val
    
    # Intelligent inference for some fields
    print("🧠 Inferring values...")
    
    # Infer status from tx_signature
    df.loc[df['tx_signature'] == 'CLOSED_BY_BOT', 'status'] = 'SIGNAL'
    df.loc[(df['tx_signature'] != 'CLOSED_BY_BOT') & (df['side'] != 'CLOSE'), 'status'] = 'OPEN'
    df.loc[(df['tx_signature'] != 'CLOSED_BY_BOT') & (df['side'] == 'CLOSE'), 'status'] = 'CLOSED'
    
    # Estimate fees (0.11% per side for Drift)
    df['fee'] = df['price'] * df['quantity'] * 0.0011
    
    # Reorder columns to match new schema
    column_order = [
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
    
    df = df[column_order]
    
    # Save enhanced version
    df.to_csv(new_file, index=False)
    print(f"✅ Enhanced trades saved to: {new_file}")
    print(f"📊 Columns: {len(df.columns)}")
    print(f"📈 Rows: {len(df)}")
    
    # Display sample
    print("\n=== Sample Enhanced Trade ===")
    print(df.iloc[-1].to_string())
    
    print("\n✅ Migration complete!")
    print(f"\nNext steps:")
    print(f"1. Review {new_file}")
    print(f"2. If satisfied, run: mv {new_file} {old_file}")
    print(f"3. Update your strategy code to pass enhanced metadata")


if __name__ == "__main__":
    migrate_trades_csv()
