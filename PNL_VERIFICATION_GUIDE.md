# Data Validation & P&L Calculation Verification Guide

## System Architecture Overview

```
Bot Trade Execution
         ↓
Validation Layer (NEW)
         ↓
P&L Calculation (DriftPnLCalculator)
         ↓
Audit Logging (Comprehensive)
         ↓
trades.csv (On-Chain Data)
```

## Validation Layer - What Gets Checked Before Recording

### 1. Price Validation
```python
✓ Must be > $1.00
✓ Must be > $0 (obviously)
✓ For BTC-PERP: Must be > $10,000
✓ Cannot be negative
```

**Example:**
- ❌ REJECTED: price = 0.001 (placeholder/invalid)
- ❌ REJECTED: price = 50 (unrealistic for BTC)
- ✅ ACCEPTED: price = 106,000 (realistic)

### 2. Quantity Validation
```python
✓ Must be > 0
✓ For PERP: Must be >= 0.001 (Drift minimum)
✓ Cannot be zero
```

**Example:**
- ❌ REJECTED: quantity = 0 (no trade)
- ❌ REJECTED: quantity = 0.0005 (below minimum)
- ✅ ACCEPTED: quantity = 0.001 (meets minimum)

### 3. Side Validation
```python
✓ Must be BUY, SELL, or CLOSE
✓ Case-insensitive
```

### 4. Risk Level Validation (SL/TP)

**For BUY Entry:**
```
Entry Price: $100,000
✓ SL must be < $100,000 (below entry)
✓ TP must be > $100,000 (above entry)
❌ REJECTED: SL=$105,000 (wrong direction)
```

**For SELL Entry:**
```
Entry Price: $100,000
✓ SL must be > $100,000 (above entry)
✓ TP must be < $100,000 (below entry)
❌ REJECTED: TP=$110,000 (wrong direction)
```

**Issue Found in Current Data:**
```csv
SELL entry @ 111,629.76
SL: 116,689.37 ✓ (above entry for short)
TP: 100,787.72 ✗ (ERROR - should be < 111,629)
```

### 5. Transaction Signature Validation
```python
✓ Must exist for all executed trades
✓ Format: 88-character base58 string
❌ Empty strings will log warning
```

---

## P&L Calculation Flow

### Gross P&L (Before Costs)
```
BUY Position:
  Gross P&L = (Close Price - Entry Price) × Quantity
  = (106,500 - 106,000) × 0.001 BTC
  = $500 × 0.001 = $0.50

SELL Position:
  Gross P&L = (Entry Price - Close Price) × Quantity
  = (106,000 - 106,500) × 0.001 BTC
  = -$500 × 0.001 = -$0.50
```

### Fees Calculation
```
Entry Fee = Entry Price × Quantity × Taker Fee Rate (0.05%)
          = 106,000 × 0.001 × 0.0005
          = $0.0530

Close Fee = Close Price × Quantity × Taker Fee Rate (0.05%)
          = 106,500 × 0.001 × 0.0005
          = $0.0533

Total Fees ≈ $0.1063
```

### Funding Payment
```
Position held: 2 hours
Funding rate: 0.00075 (8-hour rate example)

Funding = Entry Price × Quantity × Funding Rate × (Hold Hours / 8)
        = 106,000 × 0.001 × 0.00075 × (2 / 8)
        = $0.0199

For SELL: Funding direction reversed
```

### NET P&L (After All Costs)
```
NET P&L = Gross P&L - Entry Fee - Close Fee - Funding Paid
        = $0.50 - $0.0530 - $0.0533 - $0.0199
        = $0.3738

NET P&L % = $0.3738 / ($106,000 × 0.001)
          = 0.352%
```

---

## Audit Logging Example

Every trade now logs:

```
================================================================================
📊 TRADE RECORDED: CLOSE 0.001 BTC-PERP
================================================================================
Timestamp: 2025-11-05T14:30:45.123456+00:00
Market: BTC-PERP (Market Index: 1, Type: perp)
Side: CLOSE | Order Type: market
Price: $106500.00 | Quantity: 0.00100000
Risk Levels: SL=$101500.00 | TP=$115500.00

P&L Summary:
  Gross P&L: $0.50
  Entry Fee: $0.0265 | Close Fee: $0.0266
  Funding Paid: $0.0199
  Net P&L After Fees: $0.3738
  Hold Duration: 120.0 minutes

Account Context:
  Account Equity: $1000.00
  Leverage: 2.0x
  Sub-Account: 0

Execution Quality:
  Oracle Price: $106525.00
  Slippage: 25.0 bps
  Latency: 145 ms

On-Chain Data:
  TX Signature: 4RK6VFVjDqKTv9zWkvm8QfUDyHd66kr14MuHRGkJZmDWKb4tTuivEZehJ9kjnD6
  Slot: 234567890
  Block Time: 2025-11-05T14:30:45Z

Environment: devnet | Bot v1.0
================================================================================
```

---

## Verifying On-Chain Data

### Step 1: Check Transaction Signature
```bash
# Use Solana explorer:
https://explorer.solana.com/tx/{tx_signature}?cluster=devnet

# Verify:
✓ Transaction exists
✓ Status: Success (not Failed/Partial)
✓ Block timestamp matches logged time
✓ Slot number matches
```

### Step 2: Reconstruct from Drift API
```python
from driftpy.client import DriftClient

# Get trade details:
- Position entry price (confirms entry_price)
- Position close price (confirms execution_price)
- Actual fees charged
- Funding payments history
```

### Step 3: Wallet Verification
```python
# Check USDC balance change
initial_balance = $1000.00
final_balance = initial_balance + net_pnl - slippage
# Verify balance matches
```

---

## Data Quality Checklist

For each trade in trades.csv:

- [ ] **Price**: Realistic for asset (> $10k for BTC)
- [ ] **Quantity**: >= 0.001 for PERP
- [ ] **Side**: BUY/SELL/CLOSE
- [ ] **SL/TP**: Correct direction relative to entry
- [ ] **TX Signature**: Valid 88-char base58
- [ ] **P&L**: Non-zero for CLOSE trades
- [ ] **Fees**: > 0 for market orders
- [ ] **Funding**: Calculated with hold duration
- [ ] **Account Equity**: Non-zero
- [ ] **Slot**: > 0 (actual block data)
- [ ] **Block Time**: ISO timestamp

---

## Fields Now Properly Calculated

| Field | Calculation | Status |
|-------|-----------|--------|
| `pnl` | Gross P&L (Close - Entry) × Qty | ✅ Recorded |
| `fee` | Entry Fee + Close Fee | ✅ Calculated |
| `funding_paid` | Price × Qty × Rate × Hours | ✅ Calculated |
| `net_pnl_after_fees` | Gross - Fees - Funding | ✅ Calculated |
| `entry_hold_minutes` | Close Time - Entry Time | ✅ Recorded |
| `account_equity` | From broker at trade time | ⚠️ To fetch |
| `slot` | From Solana block | ⚠️ To fetch |
| `block_time` | From Drift tx data | ⚠️ To fetch |

---

## Next Steps to Complete P&L System

1. **Fetch Real Funding Rates**: Query Drift API for actual funding rate
2. **Capture Slot Numbers**: Store from transaction details
3. **Log Block Times**: Get precise timestamp from Drift
4. **Implement Wallet Verification**: Reconcile with USDC balance
5. **Add Audit Trail**: Log all intermediate calculations

See: `/trading_bot/broker/execution.py` to integrate Drift API data.
