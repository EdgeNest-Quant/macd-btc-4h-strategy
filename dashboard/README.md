# 📊 Drift MACD Trading Bot Dashboard

Professional analytics dashboard for monitoring and analyzing your BTC-PERP 4H MACD trading strategy on Drift Protocol.

## 🎯 Features

### 📊 Overview Page
- **Key Performance Metrics**: Total P&L, Win Rate, Sharpe Ratio, Max Drawdown
- **Cumulative P&L Chart**: Visual equity curve over time
- **Win/Loss Distribution**: Pie chart showing trade outcomes
- **Recent Trade Activity**: Latest 10 trades at a glance

### 💰 Performance Analytics
- **Comprehensive Metrics**: Profit Factor, Average Win/Loss, Best/Worst Trade
- **Equity Curve with Drawdown**: Dual-panel chart showing performance and risk
- **P&L Distribution**: Histogram of trade profitability
- **Trade Duration Analysis**: Box plot of position hold times

### 📈 Trade Analysis
- **Trade Statistics**: Long/Short counts, position sizes, hold times
- **Trade Timeline**: Interactive scatter plot of all entries/exits
- **Long vs Short Performance**: Bar chart comparing directional bias
- **Hourly Distribution**: When your trades are executed

### ⚠️ Risk Metrics
- **Risk-Adjusted Returns**: Sharpe, Sortino, VaR, Expected Shortfall
- **Drawdown Analysis**: Rolling volatility and drawdown charts
- **Risk Exposure**: Current open positions and risk summary

### 🔴 Live Monitoring
- **Current Positions**: Real-time view of open trades
- **Recent Activity**: Latest trade executions
- **Today's Summary**: Daily P&L and trade count
- **Log Events**: Real-time bot activity feed

### 📜 Trade History
- **Complete Trade Log**: Searchable, filterable table of all trades
- **Advanced Filters**: By status, side, date range
- **CSV Export**: Download filtered data for external analysis

---

## 🚀 Quick Start

### Option 1: Using the Launch Script (Recommended)

```bash
# From project root
./run_dashboard.sh
```

The dashboard will automatically:
- Activate virtual environment
- Install dependencies
- Launch on http://localhost:8501

### Option 2: Manual Launch

```bash
# Activate virtual environment
source .venv/bin/activate

# Install dependencies
pip install streamlit plotly pandas numpy

# Launch dashboard
streamlit run dashboard/app.py
```

---

## 📁 Data Sources

The dashboard reads from:

1. **`trades.csv`** - Trade execution data
   - Entry/exit prices
   - Position sizes
   - P&L calculations
   - Timestamps and metadata

2. **`logs/`** - Bot activity logs
   - Strategy signals
   - Position management
   - Error messages
   - System events

---

## 🎨 Dashboard Pages

### Navigation
Use the sidebar to switch between pages:

```
📊 Overview           - High-level performance summary
💰 Performance        - Detailed P&L analytics
📈 Trade Analysis     - Trade statistics and patterns
⚠️ Risk Metrics       - Risk-adjusted performance
🔴 Live Monitoring    - Real-time bot status
📜 Trade History      - Complete trade log
```

---

## 📊 Key Metrics Explained

### Performance Metrics

- **Total P&L**: Sum of all realized profits/losses
- **Win Rate**: Percentage of profitable closed trades
- **Profit Factor**: Gross profit ÷ Gross loss
- **Average Win/Loss**: Mean P&L of winning/losing trades

### Risk Metrics

- **Sharpe Ratio**: Risk-adjusted return (higher is better)
  - `< 0`: Losing money
  - `0-1`: Poor risk-adjusted returns
  - `1-2`: Good performance
  - `> 2`: Excellent performance

- **Sortino Ratio**: Like Sharpe but only penalizes downside volatility

- **Max Drawdown**: Largest peak-to-trough decline
  - Measures worst-case loss scenario
  - Lower is better

- **VaR (95%)**: Value at Risk - expected loss at 95% confidence
  - "You won't lose more than this in 95% of trades"

---

## 🔧 Configuration

### Auto-Refresh
Enable auto-refresh on the Live Monitoring page to update every 30 seconds.

### Date Range Filters
On Trade History page, filter by date range to analyze specific time periods.

### Export Data
Download filtered trade data as CSV for external analysis in Excel/Python.

---

## 📈 Usage Tips

### For Day Trading
1. Monitor **Live Monitoring** page during trading hours
2. Check **Today's Summary** for daily performance
3. Watch for log events indicating new signals

### For Strategy Analysis
1. Review **Performance Analytics** for overall profitability
2. Check **Risk Metrics** to ensure acceptable drawdown
3. Analyze **Trade Analysis** to identify patterns

### For Risk Management
1. Monitor **Max Drawdown** - exit if exceeds threshold
2. Check **Open Positions** on Live Monitoring
3. Review **Risk Exposure** table for position sizing

---

## 🐛 Troubleshooting

### Dashboard won't start
```bash
# Check if streamlit is installed
pip list | grep streamlit

# Reinstall dependencies
pip install --upgrade streamlit plotly
```

### No data showing
```bash
# Verify trades.csv exists
ls -lh trades.csv

# Check file has data
head trades.csv
```

### Charts not rendering
- Clear browser cache
- Try different browser (Chrome recommended)
- Check console for JavaScript errors (F12)

---

## 📊 Sample Screenshots

### Overview Page
Shows total P&L, win rate, equity curve, and recent trades.

### Performance Analytics
Detailed breakdown of profitability with equity curve and drawdown analysis.

### Live Monitoring
Real-time position tracking with log event feed.

---

## 🔄 Data Updates

The dashboard reads data on each page load:
- **Manual Refresh**: Click browser refresh or press F5
- **Auto-Refresh**: Enable on Live Monitoring page (30s interval)
- **Trade Data**: Automatically updates when bot records new trades

---

## 🚀 Deployment Options

### Local Deployment (Default)
```bash
streamlit run dashboard/app.py --server.port=8501
```

### Network Access (Share with Team)
```bash
streamlit run dashboard/app.py --server.address=0.0.0.0 --server.port=8501
```
Access from other devices: `http://YOUR_IP:8501`

### Streamlit Cloud (Public Hosting)
1. Push code to GitHub
2. Go to https://share.streamlit.io
3. Connect repository
4. Deploy `dashboard/app.py`

---

## 📝 Notes

- Dashboard is **read-only** - it cannot modify trades or bot settings
- All metrics are calculated from historical data in `trades.csv`
- Log parsing shows recent events from latest log file
- Performance calculations assume no external deposits/withdrawals

---

## 🤖 Strategy Information

**Symbol**: BTC-PERP  
**Timeframe**: 4 Hours  
**Strategy**: MACD Momentum (6, 10, 2) with 168 EMA filter  
**Environment**: Solana Devnet  

---

## 📞 Support

For issues or questions:
1. Check bot logs in `logs/` directory
2. Verify `trades.csv` format matches expected schema
3. Review bot configuration in `trading_bot/config.py`

---

**Version**: 1.0.0  
**Last Updated**: October 21, 2025
