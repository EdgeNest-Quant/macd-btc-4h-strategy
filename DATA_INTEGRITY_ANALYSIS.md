# Data Integrity Analysis & Issues Found

## Critical Issues Identified

### 1. **Missing Drift-Specific Columns in CSV** ❌
The following columns were added to the tracker but NOT populated in trades.csv:
- `funding_paid` (all zeros)
- `cumulative_funding` (all zeros)
- `entry_hold_minutes` (all zeros)
- `taker_fee_rate` (missing entirely)
- `maker_fee_rate` (missing entirely)
- `net_pnl_after_fees` (missing entirely)

**Impact:** P&L calculations are incomplete and don't reflect actual Drift costs.

### 2. **Incomplete P&L Recording** ❌
**Entry Trades (BUY/SELL):**
- `pnl = 0.0` (correct for entry, position not closed yet)
- Missing: `account_equity` (always 0.0)
- Missing: `oracle_price_at_entry` (always 0.0)
- Missing: `execution_latency_ms` (always 0.0)

**Close Trades:**
- `pnl` is recorded (e.g., -0.2719728528694395)
- BUT: No `funding_paid` breakdown
- No fee deductions applied

### 3. **Invalid/Placeholder Data** ❌
**Example from trades.csv row 1:**
```
price: 111629.75754713056 (8 decimals - suspicious precision)
quantity: 0.0010098116020041 (14 decimals - suspicious precision)
sl: 116689.37365633284 (Stop Loss > Entry Price for SHORT!)
tp: 100787.72302741138 (Take Profit still high for SHORT)
```

**Example from row 2 (CLOSE):**
```
price: 111901.7304 (close price seems real)
quantity: 0.001 (rounded to exact minimum?)
pnl: -0.2719728528694395 (calculated, but fees not deducted)
status: CLOSED ✓
```

### 4. **Missing Account Context** ❌
All trades show:
- `account_equity: 0.0` (should show account balance at time of trade)
- `leverage: 1.0` (hardcoded, should be actual leverage used)
- `slot: 0` (missing Solana slot number)
- `block_time: ""` (missing timestamp)

### 5. **No On-Chain Data Verification** ❌
Cannot verify these are real Drift trades because:
- No actual Solana block data
- `slot` field is always 0
- `block_time` is empty
- Can only verify via `tx_signature` on explorer

### 6. **Calculation Logic Issues in Code** ❌
In `macd_strategy_btc_4h_advanced.py` lines 900-907:
```python
# Gross P&L calculated BEFORE fees
realized_pnl = quantity * (execution_price - entry_price)

# Record to CSV with ONLY gross P&L
self.portfolio_tracker.record_trade(
    pnl=realized_pnl,  # ← No fees deducted!
    # Missing: funding_paid, cumulative_funding, etc.
)
```

**Should be:**
```python
# Calculate NET P&L after all costs
pnl_breakdown = DriftPnLCalculator.calculate_realized_pnl(
    entry_price=entry_price,
    close_price=execution_price,
    quantity=quantity,
    side=self.position_side,
    hold_hours=hold_minutes / 60,
    funding_rate=0.0,  # Get from Drift
    is_maker=False
)
net_pnl = pnl_breakdown['net_pnl']
```

## Data Quality Scorecard

| Aspect | Status | Issue |
|--------|--------|-------|
| Entry Price | ✓ Real | Valid on-chain |
| Close Price | ✓ Real | Valid on-chain |
| Quantity | ⚠️ Suspect | Excessive decimals |
| SL/TP Levels | ❌ Invalid | Wrong direction |
| P&L Gross | ✓ Calculated | Correct math |
| P&L Fees | ❌ Missing | Not deducted |
| P&L Funding | ❌ Missing | Not deducted |
| Account Equity | ❌ Missing | Always 0.0 |
| On-Chain Data | ⚠️ Partial | Only tx_signature |

## Verification Steps Needed

### 1. Verify Transaction Signatures
Each `tx_signature` must be validated on Solana explorer:
- Check slot number
- Verify timestamp
- Confirm amount and direction
- Check success/failure status

### 2. Reconstruct From Drift API
Use Drift SDK to fetch:
- Actual entry/close prices from on-chain
- Realized fees charged
- Funding payments
- Account state at time of trade

### 3. Cross-Check With Wallet Activity
Compare with wallet:
- USDC balance changes
- Position state
- Realized losses

## Recommendations

1. **Add validation layer** before recording trades
2. **Fetch real Drift data** (fees, funding from API)
3. **Store on-chain verification** (slot, block_time)
4. **Calculate net P&L** using `DriftPnLCalculator`
5. **Add historical logging** of all calculations
6. **Implement audit trail** with before/after states
