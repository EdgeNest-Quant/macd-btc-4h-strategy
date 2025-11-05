# P&L Calculation Quick Reference

## Formula Sheet

### Gross P&L
**LONG Position:**
```
Gross P&L = (Close Price - Entry Price) × Quantity
```

**SHORT Position:**
```
Gross P&L = (Entry Price - Close Price) × Quantity
```

### Drift Protocol Fees
```
Entry Fee = Entry Price × Quantity × 0.0005  (0.05% taker)
Close Fee = Close Price × Quantity × 0.0005  (0.05% taker)

Total Fees = Entry Fee + Close Fee
```

### Funding Payments (Hourly on Drift)
```
Funding Payment = Entry Price × Quantity × Funding Rate × (Hold Hours)

For LONG: Positive funding = you pay
For SHORT: Negative funding (reversed direction)
```

### Net P&L (True Profit)
```
Net P&L = Gross P&L - Entry Fee - Close Fee - Funding Paid

Net P&L % = (Net P&L / Notional Value) × 100%
where Notional Value = Entry Price × Quantity
```

---

## Practical Examples

### Example 1: Profitable LONG
```
Entry:  BTC-PERP @ $100,000 | Qty: 0.1 BTC
Close:  BTC-PERP @ $101,000 | After 4 hours
Funding: 0.00005 (8-hr rate)

Gross P&L:
  (101,000 - 100,000) × 0.1 = $100

Fees:
  Entry: 100,000 × 0.1 × 0.0005 = $5.00
  Close: 101,000 × 0.1 × 0.0005 = $5.05

Funding (LONG, positive = pay):
  100,000 × 0.1 × 0.00005 × 4 = $2.00

NET P&L = $100 - $5.00 - $5.05 - $2.00 = $87.95
Net P&L % = $87.95 / $10,000 = 0.88%
```

### Example 2: Losing SHORT
```
Entry:  BTC-PERP @ $100,000 | Qty: 0.1 BTC (SHORT)
Close:  BTC-PERP @ $100,500 | After 8 hours
Funding: 0.00005 (8-hr rate)

Gross P&L (SHORT):
  (100,000 - 100,500) × 0.1 = -$50

Fees:
  Entry: 100,000 × 0.1 × 0.0005 = $5.00
  Close: 100,500 × 0.1 × 0.0005 = $5.03

Funding (SHORT, reversed - negative means receive):
  -(100,000 × 0.1 × 0.00005 × 8) = -$4.00 (you receive $4)

NET P&L = -$50 - $5.00 - $5.03 - (-$4.00) = -$56.03
Net P&L % = -$56.03 / $10,000 = -0.56%
```

---

## Code Implementation

### Using DriftPnLCalculator
```python
from trading_bot.portfolio.portfolio_tracker import DriftPnLCalculator

pnl = DriftPnLCalculator.calculate_realized_pnl(
    entry_price=100000,
    close_price=101000,
    quantity=0.1,
    side='BUY',
    hold_hours=4,
    funding_rate=0.00005,
    is_maker=False
)

print(f"Gross P&L: ${pnl['gross_pnl']:.2f}")
print(f"Net P&L: ${pnl['net_pnl']:.2f}")
print(f"Net P&L %: {pnl['net_pnl_pct']:.2f}%")

# Output:
# Gross P&L: $100.00
# Net P&L: $87.95
# Net P&L %: 0.88%
```

### Formatted Report
```python
report = DriftPnLCalculator.format_pnl_report(pnl)
print(report)

# Output:
# P&L Breakdown:
#   Gross P&L:        $100.00
#   Entry Fee:        $5.00
#   Close Fee:        $5.05
#   Funding Paid:     $2.00
#   ────────────────────────
#   Total Costs:      $12.05
#   NET P&L:          $87.95 (+0.88%)
```

---

## Data Fields in trades.csv

### Calculated by Bot
| Field | Meaning | Example |
|-------|---------|---------|
| `pnl` | Gross P&L before costs | $100.00 |
| `fee` | Total entry + close fees | $10.05 |
| `funding_paid` | Hourly funding cost | $2.00 |
| `entry_hold_minutes` | Duration of trade | 240 |
| `net_pnl_after_fees` | True profit | $87.95 |

### Key Verification
```
net_pnl_after_fees = pnl - fee - funding_paid
87.95 = 100.00 - 10.05 - 2.00 ✓
```

---

## Drift Fee Structure (Hardcoded)

```python
TAKER_FEE = 0.0005   # 0.05%
MAKER_FEE = 0.0002   # 0.02%

# All market orders are TAKER
# Limit orders can be MAKER (better rates)
```

**Why this matters:**
- Market orders cost more (0.05% vs 0.02%)
- Maker rebates incentivize limit orders
- Always factor fees into exit decisions

---

## Audit Trail Example

From bot logs when closing position:

```
================================================================================
📊 TRADE RECORDED: CLOSE 0.1 BTC-PERP
================================================================================
Price: $101000.00 | Quantity: 0.10000000
P&L Summary:
  Gross P&L: $100.00
  Entry Fee: $5.00 | Close Fee: $5.05
  Funding Paid: $2.00
  Net P&L After Fees: $87.95
  Hold Duration: 240.0 minutes
================================================================================
```

---

## Common Mistakes to Avoid

❌ **Mistake 1:** Using gross P&L without fee deduction
```python
profit = close_price - entry_price  # WRONG!
```
✅ **Correct:**
```python
profit = close_price - entry_price - (fees/quantity) - funding
```

❌ **Mistake 2:** Ignoring funding for short holds
```python
pnl = (close - entry) * qty  # Missing 2+ hours of funding!
```
✅ **Correct:**
```python
pnl = (close - entry) * qty - fees - funding
```

❌ **Mistake 3:** Wrong fee direction for shorts
```python
short_pnl = (entry - close) * qty - fees  # Funding direction wrong!
```
✅ **Correct:**
```python
if short:
    short_pnl = (entry - close) * qty - fees - (-funding)  # funding reversed
```

---

## Verification Checklist

Before declaring a trade profitable:

- [ ] Entry price > $10,000 (realistic BTC)
- [ ] Close price > $10,000 (realistic BTC)
- [ ] Quantity >= 0.001 (Drift minimum)
- [ ] Hold duration makes sense (not 0 seconds)
- [ ] Fees > 0 (should always have fees)
- [ ] Funding calculated for duration
- [ ] Net P&L < Gross P&L (fees reduce profit)
- [ ] TX signature exists & is valid format
- [ ] P&L % reasonable for hold time

✅ If all checks pass → Trade is authentic!

