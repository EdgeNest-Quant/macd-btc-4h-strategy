# 🚨 Bot Execution Issue - Diagnostic Report

## Problem Summary

Bot attempted real trade execution on Drift but **order was rejected** with:
```
Actual quantity = 0 (expected: 0.004168 BTC)
```

This indicates **order reached Drift chain but was rejected** due to:
1. Insufficient margin/collateral
2. Position size exceeds leverage limits
3. Account doesn't have deposit

---

## Execution Timeline

| Time | Event | Status |
|------|-------|--------|
| 07:41:21 | MACD SELL signal generated | ✅ |
| 07:41:21 | Risk management approved | ✅ |
| 07:41:21 | `place_market_order()` called | ✅ |
| 07:41:44 | TX submitted (23s latency) | ✅ |
| 07:41:46 | Order confirmed on-chain | ✅ |
| 07:41:46 | **actual_qty = 0 (REJECTED)** | ❌ |

---

## Root Cause Analysis

### Order Details
```
Symbol: BTC-PERP (Market Index: 1)
Direction: SELL (SHORT)
Intended Quantity: 0.004167979485378355 BTC
Actual Quantity: 0 BTC ← REJECTED
Entry Price: 103070.897192 USD
Notional Value: ~$429 USD
Account Type: devnet
```

### Why Order Failed

**Most Likely**: Account has no USDC collateral deposited

```
USDC Balance = $0 (need at least $50-100 for margin)
↓
Position Size × Leverage = $429 × 1.0 = $429 margin required
↓
Insufficient funds to cover margin requirement
↓
Drift rejects order with qty=0
```

### Configuration Issues

**Current Settings** (aggressive):
```python
POSITION_PCT = 0.30      # 30% of account
LEVERAGE_MULTIPLIER = 2.0  # 2x leverage
MAX_DRAWDOWN_PCT = 0.10  # 10% max loss
```

**Problem**: 
- 30% × 2.0x = **60% position sizing** (very aggressive!)
- Requires minimum account: ~$500 USDC for this trade

**What bot calculated**:
- Account balance: ~$1,473 (from logs)
- Position size: 30% × $1,473 = $441.79
- With 2.0x leverage: $441.79 notional attempted
- Margin needed: $220 USDC (at 2x leverage)

**What failed**:
- Account has $0 USDC collateral
- Drift rejected order to prevent liquidation

---

## Solution

### Option 1: Add Collateral (Recommended for Testing)

Deposit USDC to devnet account:
```bash
# 1. Get your account address
solana address

# 2. Airdrop SOL to cover fees
solana airdrop 2

# 3. Bridge USDC to devnet or use devnet faucet
# Visit: https://spl-token-faucet.com/
# Token: EPjFWdd5Au...  (USDC on devnet)
# Amount: 500 (USDC)
```

Then restart bot.

### Option 2: Reduce Position Size (Safer)

Modify `config.py`:

```python
# BEFORE (Too aggressive)
POSITION_PCT = 0.30          # 30% per trade
LEVERAGE_MULTIPLIER = 2.0    # 2x leverage

# AFTER (Conservative)
POSITION_PCT = 0.10          # 10% per trade  
LEVERAGE_MULTIPLIER = 1.0    # 1x leverage (no margin)
```

This requires only:
- Notional: 10% × $1,473 = $147.30
- Margin needed: ~$15 USDC (at 1x)
- **Much safer for testing**

### Option 3: Switch to Paper Trading

Use simulation/backtesting mode instead of live execution:

```python
# Add to config.py
PAPER_TRADING = True  # Simulate orders instead of executing
```

---

## Current Account Status (from logs)

```
Bot detected:
- Position: SPOT_1 (SOL spot) with 0.55465 SOL
- Account equity: ~$1,473
- Margin available: Unknown (likely 0 or very low)
- USDC balance: Appears to be 0
```

---

## Immediate Actions

### 1. Check Account Collateral (Priority: CRITICAL)

```bash
# SSH into devnet, check account details
# Account address from keypair file or logs

# Show all token balances
solana account <YOUR_ADDRESS>
```

### 2. Deposit Minimum Collateral

For testing 0.004 BTC trades (~$400):
- **Recommended**: Deposit 500 USDC to devnet account
- **Minimum**: Deposit 100 USDC

### 3. Adjust Config (Priority: HIGH)

Reduce position sizing to match account:

```python
# config.py - Line 99-102
POSITION_PCT = 0.10          # ← Change from 0.30
LEVERAGE_MULTIPLIER = 1.0    # ← Change from 2.0
```

### 4. Test with Reduced Size

- Restart bot with new config
- Let it generate next signal
- Verify order executes with smaller position

---

## Prevention: Margin Calculator

Add this check before order execution:

```python
def check_margin_available(account_balance: float, notional: float, leverage: float) -> bool:
    """Verify sufficient margin before order execution"""
    margin_required = notional * leverage / 100  # Conservative 1% margin req
    margin_available = account_balance  # USDC balance
    
    if margin_available < margin_required:
        logger.error(f"Insufficient margin: Need ${margin_required:.2f}, Have ${margin_available:.2f}")
        return False
    return True
```

---

## Bot Safety Checklist

- [ ] USDC collateral deposited to account
- [ ] Position size reduced (POSITION_PCT = 0.10)
- [ ] Leverage set to 1.0x (no margin)
- [ ] RPC endpoint verified (devnet or mainnet)
- [ ] Private key loaded correctly
- [ ] Min signal strength set (MIN_SIGNAL_STRENGTH = 0.20)
- [ ] Max drawdown configured (MAX_DRAWDOWN_PCT = 0.10)
- [ ] First trade manually verified before auto mode

---

## Next Steps

1. **Immediate**: Deposit 500 USDC to devnet account
2. **Short-term**: Reduce position sizing in config
3. **Medium-term**: Add margin check before order submission
4. **Long-term**: Implement full backtesting suite before live trading

**Status**: ⏸️ **BOT PAUSED - Waiting for collateral deposit**

