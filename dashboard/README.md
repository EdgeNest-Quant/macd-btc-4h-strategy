# Drift Protocol Trading Bot Dashboard

Real-time analytics dashboard for the BTC-PERP 4H MACD trading strategy on Drift Protocol. Displays verified P&L calculations with real account balance from the Drift Protocol.

## Features

✅ **Real Account Balance** - Fetches live balance directly from Drift Protocol via RPC
✅ **Verified P&L** - Calculates net profit/loss including:
  - Gross P&L (before costs)
  - Trading fees (0.05% taker rate)
  - Funding rate payments (hourly)
  - Net P&L (after all costs)

✅ **Trade Analytics** - Comprehensive trade statistics:
  - Win rate and trade distribution
  - Largest wins/losses
  - Trade duration analysis
  - Execution quality metrics

✅ **Data Integrity** - Validates all trades:
  - Checks Solana transaction signatures
  - Validates price and quantity data
  - Confirms cost tracking
  - Data quality scoring

✅ **Real-Time Updates** - Auto-refreshes data every 60 seconds

## Installation

### Prerequisites
- Python 3.9+
- Trading bot configured and running
- Drift Protocol RPC endpoint
- Private key configured in `.env`

### Setup

```bash
cd dashboard

# Install dependencies
pip install -r requirements.txt
```

## Running the Dashboard

### Start Streamlit App

```bash
streamlit run app.py
```

The dashboard will be available at `http://localhost:8501`

### With Custom RPC (Optional)

```bash
SOLANA_RPC_URL=https://your-rpc.com streamlit run app.py
```

### Background Execution

```bash
# Run in background
nohup streamlit run app.py &

# Or with Docker
docker run -p 8501:8501 -v $(pwd):/app streamlit run app.py
```

## Dashboard Sections

### 1. Account Overview
- **Account Balance**: Real balance from Drift Protocol
- **Net P&L**: Total profit/loss after fees and funding
- **Win Rate**: Percentage of profitable trades
- **Total Trades**: Count of executed trades

### 2. P&L Breakdown (Closed Trades)
- **Gross P&L**: Raw profit before costs
- **Trading Fees**: Entry + close fees
- **Funding Paid**: Hourly funding rate payments
- **Largest Win/Loss**: Best and worst individual trades

### 3. Trade Details Table
- Last 20 trades with:
  - Entry/close prices
  - Position side (BUY/SELL/CLOSE)
  - P&L for each trade
  - Fees and funding costs
  - Trade status

### 4. Analytics & Charts
- **P&L Over Time**: Cumulative P&L line chart
- **Trade Distribution**: Win/loss pie chart + side distribution
- **Win/Loss Analysis**: P&L distribution box plot + statistics
- **Execution Quality**: Latency and slippage distributions

### 5. Data Integrity & Audit Trail
- Valid transaction signature verification
- Cost tracking confirmation
- Data quality score (0-100%)
- Sample transaction details with Solana TX signatures

## Data Sources

### Real-Time Balance
```
Source: Drift Protocol SDK
Method: DriftOrderExecutor.get_account_balance()
Update Frequency: On-demand (cached 60s)
```

### Trade Data
```
Source: trades.csv (from trading bot)
Columns: 35 (including all Drift-specific costs)
Update Frequency: After each trade executes
```

### Blockchain Verification
```
Source: Solana blockchain
Data: Transaction signatures, slots, block times
Purpose: Audit trail and trade authenticity
```

## Key Metrics Explained

### Net P&L Calculation
```
Net P&L = Gross P&L - Entry Fee - Close Fee - Funding Paid

Where:
- Gross P&L = (Close Price - Entry Price) × Quantity
- Entry Fee = Entry Notional × 0.05%
- Close Fee = Close Notional × 0.05%
- Funding Paid = Notional × Funding Rate × Hold Hours
```

### Win Rate
```
Win Rate (%) = (Winning Trades / Closed Trades) × 100

Where:
- Winning Trade = P&L > $0
- Losing Trade = P&L < $0
```

### Data Quality Score
```
Quality Score (%) = (Passed Checks / Total Checks) × 100

Checks:
1. All prices > $0
2. All quantities > 0
3. All sides in [BUY, SELL, CLOSE]
```

## Environment Variables

Required in `.env`:
```
PRIVATE_KEY=your_base58_private_key
SOLANA_RPC_URL=https://your-rpc-endpoint.com
SUB_ACCOUNT_ID=0
TRADES_FILE=../trades.csv
TIMEZONE=UTC
```

## Troubleshooting

### Dashboard Not Loading
```bash
# Check if Streamlit is running
ps aux | grep streamlit

# Kill existing process and restart
pkill -f streamlit
streamlit run app.py
```

### Real Balance Not Updating
- Verify RPC endpoint is accessible
- Check private key is correct in `.env`
- Ensure Drift subaccount exists
- Review logs: `tail -f ../logs/*.log`

### Missing Trade Data
- Ensure trading bot is running
- Check `trades.csv` exists in parent directory
- Verify file has correct columns

### Data Quality Score Low
- Check for negative prices in CSV
- Verify all quantities > 0
- Confirm trade sides are valid (BUY/SELL/CLOSE)

## Performance Optimization

### For Slow Dashboard Load
- Reduce data retention: Archive old trades monthly
- Clear browser cache: `Ctrl+Shift+Delete`
- Increase cache TTL in `load_trades_data()`

### For High RPC Latency
- Use faster RPC endpoint
- Implement local caching
- Increase timeout values

## Security Notes

⚠️ **Sensitive Data**
- Private key never sent to dashboard frontend
- All Drift API calls use Rust backend
- Dashboard communicates with local trading bot only

✅ **Best Practices**
- Run dashboard on isolated network
- Use read-only subaccounts when possible
- Rotate API keys regularly
- Monitor transaction signatures for authenticity

## Support & Documentation

For detailed P&L calculation logic, see:
- `PNL_QUICK_REFERENCE.md` - Formula sheet
- `PNL_VERIFICATION_GUIDE.md` - Technical reference
- `DATA_INTEGRITY_ANALYSIS.md` - Data validation details

## License

MIT License - See LICENSE file for details
