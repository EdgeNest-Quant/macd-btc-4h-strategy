# Drift Protocol Trading Bot

A sophisticated cryptocurrency trading bot built for Drift Protocol on Solana, featuring Supertrend and EMA strategy with comprehensive risk management.

## 🌟 Features

- **Drift Protocol Integration**: Native support for Solana's premier perpetual DEX
- **Advanced Strategy**: Supertrend + EMA multi-timeframe strategy
- **Risk Management**: Position sizing, stop losses, and portfolio protection
- **Real-time Trading**: Async/await architecture for optimal performance
- **Comprehensive Logging**: Detailed trade tracking and performance analytics
- **Testnet Support**: Safe testing environment with devnet integration

## 📁 Project Architecture

```
dex_trading_bot/
├── config.py                  # Drift & Solana configuration
├── main.py                    # Async main entry point
├── logger.py                  # Advanced logging system
├── .env                       # Environment variables (create from .env.example)
├── .env.example              # Configuration template
├── requirements.txt          # Python dependencies
├── trades.csv                # Trade history (auto-generated)
├── logs/                     # Log files directory
│
├── data/
│   ├── __init__.py
│   └── data_handler.py       # Drift data fetching & synthetic OHLCV
│
├── indicators/
│   ├── __init__.py
│   └── indicators.py         # Technical indicators (EMA, Supertrend, ATR)
│
├── broker/
│   ├── __init__.py
│   └── execution.py          # Drift order execution & position management
│
├── risk/
│   ├── __init__.py
│   └── risk_manager.py       # Position sizing & risk calculations
│
├── strategies/
│   ├── __init__.py
│   └── strategy.py           # Drift-optimized Supertrend + EMA strategy
│
└── portfolio/
    ├── __init__.py
    └── portfolio_tracker.py  # Trade recording & P&L tracking
```

## 🚀 Quick Start

### 1. Prerequisites

- Python 3.8 or higher
- Solana wallet with devnet SOL
- Basic understanding of Drift Protocol

### 2. Installation

```bash
# Clone and navigate to project
cd dex_trading_bot

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Configuration

```bash
# Copy configuration template
cp .env.example .env

# Edit configuration with your details
nano .env  # or use your preferred editor
```

Required `.env` variables:
```bash
# Your Solana private key (Base58 string or file path)
PRIVATE_KEY=your_base58_private_key_here

# Solana RPC endpoint (devnet for testing)
SOLANA_RPC_URL=https://api.devnet.solana.com

# Environment (devnet/mainnet)
DRIFT_ENV=devnet
```

### 4. Get Testnet Funds

```bash
# Get your wallet address first
# Then request testnet SOL
solana airdrop 5 <YOUR_WALLET_ADDRESS> --url devnet

# Verify balance
solana balance <YOUR_WALLET_ADDRESS> --url devnet
```

### 5. Run the Bot

```bash
# Activate virtual environment if not already active
source venv/bin/activate

# Run the trading bot
python -m dex_trading_bot.main
```

## ⚙️ Configuration Options

### Trading Parameters

Edit `config.py` or use environment variables:

```python
# Markets to trade
LIST_OF_TICKERS = ["SOL-PERP", "BTC-PERP", "ETH-PERP"]

# Risk management
STOP_PERC = 2              # 2% stop loss
MAX_POSITION_PCT = 0.01    # 1% of account per position
SAFETY_MARGIN = 0.95       # Use 95% of available balance

# Strategy parameters
EMA_LENGTH = 10            # EMA period
SUPERTREND_LENGTH = 10     # Supertrend period
ATR_LENGTH = 14            # ATR period for volatility

# Execution
STRATEGY_CHECK_INTERVAL = 60  # Check every 60 seconds
```

### RPC Configuration

For better performance, consider using a premium RPC provider:

```bash
# Helius
SOLANA_RPC_URL=https://rpc.helius.xyz/?api-key=YOUR_API_KEY

# QuickNode
SOLANA_RPC_URL=https://your-endpoint.solana-devnet.quiknode.pro/YOUR_TOKEN/

# Alchemy
SOLANA_RPC_URL=https://solana-devnet.g.alchemy.com/v2/YOUR_API_KEY
```

## 📊 Strategy Details

### Supertrend + EMA Strategy

**Entry Conditions (Long):**
- Supertrend indicator is bullish (> 0)
- Daily EMA is below current price (uptrend confirmation)
- Sufficient account balance for position sizing

**Exit Conditions:**
- Supertrend indicator turns bearish (< 0)
- Daily EMA is above current price (downtrend signal)
- Stop loss triggered (2% below entry by default)

**Multi-timeframe Analysis:**
- **1-minute**: Entry/exit timing
- **1-hour**: Signal confirmation
- **1-day**: Trend filter

### Risk Management

- **Position Sizing**: 1% of account per trade by default
- **Stop Losses**: ATR-based or percentage-based stops
- **Portfolio Limits**: Maximum allocation per market
- **Equal Allocation**: Distributes capital across all markets

## 📈 Monitoring & Analytics

### Real-time Monitoring

The bot provides comprehensive logging:

```bash
# View logs in real-time
tail -f logs/drift_supertrend_ema_strategy_YYYYMMDD.log

# Monitor specific components
grep "Trade recorded" logs/*.log
grep "ERROR" logs/*.log
```

### Performance Tracking

```python
# View trading performance
from dex_trading_bot.portfolio.portfolio_tracker import DriftPortfolioTracker

tracker = DriftPortfolioTracker()
tracker.print_trades(days=7)  # Last 7 days
pnl_stats = tracker.calculate_pnl()
print(f"Total P&L: ${pnl_stats['realized_pnl']:.2f}")
```

## 🔧 Advanced Usage

### Custom Strategy Development

Extend the base strategy:

```python
from dex_trading_bot.strategies.strategy import DriftSupertrendEMAStrategy

class MyCustomStrategy(DriftSupertrendEMAStrategy):
    def check_buy_condition(self, hist_df_hourly, hist_df_daily):
        # Add your custom logic here
        base_condition = super().check_buy_condition(hist_df_hourly, hist_df_daily)
        
        # Example: Add volume filter
        volume_condition = hist_df_hourly['volume'].iloc[-1] > hist_df_hourly['volume'].mean()
        
        return base_condition and volume_condition
```

### Multiple Subaccounts

```python
# Trade with different subaccounts
executor1 = DriftOrderExecutor(private_key, sub_account_id=0)
executor2 = DriftOrderExecutor(private_key, sub_account_id=1)
```

## 🛡️ Safety Features

### Built-in Protections

- **Connection monitoring**: Automatic reconnection on RPC failures
- **Position limits**: Prevents over-leveraging
- **Emergency shutdown**: Graceful position closure on exit
- **Transaction retry**: Handles Solana network congestion
- **Balance checks**: Prevents insufficient fund errors

### Testing Mode

Always test on devnet first:

```bash
# Ensure devnet configuration
DRIFT_ENV=devnet
SOLANA_RPC_URL=https://api.devnet.solana.com
```

## 🐛 Troubleshooting

### Common Issues

**1. Private Key Errors**
```bash
# Ensure private key is properly formatted
# Base58 string or path to .json keypair file
PRIVATE_KEY=your_base58_string_here
# or
PRIVATE_KEY=/path/to/keypair.json
```

**2. RPC Connection Issues**
```bash
# Try different RPC endpoints
# Public RPCs may be rate-limited
SOLANA_RPC_URL=https://api.devnet.solana.com
```

**3. Insufficient Balance**
```bash
# Get more devnet SOL
solana airdrop 5 <YOUR_WALLET> --url devnet
```

**4. Market Data Issues**
```bash
# Check if markets are available
# Some markets may not exist on devnet
```

### Debug Mode

Enable detailed logging:

```bash
# In .env file
DEBUG=true

# Or run with verbose logging
python -m dex_trading_bot.main --debug
```

## 📝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature-name`
3. Make your changes and test thoroughly on devnet
4. Submit a pull request with detailed description

## ⚠️ Disclaimers

- **Educational Purpose**: This bot is for educational and research purposes
- **Risk Warning**: Trading involves substantial risk of loss
- **No Guarantees**: Past performance doesn't guarantee future results
- **Test First**: Always test strategies on devnet before mainnet
- **Regulatory Compliance**: Ensure compliance with local regulations

## 📄 License

MIT License - see LICENSE file for details

## 🔗 Resources

- [Drift Protocol Documentation](https://docs.drift.trade/)
- [Solana Documentation](https://docs.solana.com/)
- [DriftPy SDK](https://github.com/drift-labs/driftpy)
- [Technical Analysis Library](https://github.com/twopirllc/pandas-ta)

---

**Happy Trading! 🚀**

*Remember: Never risk more than you can afford to lose*

Create empty `__init__.py` files in each subdirectory:

```bash
touch data/__init__.py
touch indicators/__init__.py
touch broker/__init__.py
touch risk/__init__.py
touch strategies/__init__.py
touch portfolio/__init__.py
```

### 3. Create `.env` File

Create a `.env` file in the root directory:

```bash
API_KEY=your_alpaca_api_key_here
SECRET_KEY=your_alpaca_secret_key_here
```

### 4. Install Dependencies

```bash
pip install alpaca-py pandas pandas-ta pendulum python-dotenv
```

### 5. Copy Module Files

Copy each module file into its respective location:
- `config.py` → root
- `logger.py` → root
- `main.py` → root
- `data_handler.py` → data/
- `indicators.py` → indicators/
- `execution.py` → broker/
- `risk_manager.py` → risk/
- `strategy.py` → strategies/
- `portfolio_tracker.py` → portfolio/

## 🎯 How It Works

### Module Responsibilities

1. **config.py**: Central configuration
   - API credentials
   - Trading parameters
   - Strategy settings

2. **logger.py**: Logging setup
   - Creates daily log files
   - Tracks all trading activities

3. **data/data_handler.py**: Data fetching
   - Fetches historical crypto data from Alpaca
   - Converts timezones
   - Adds technical indicators

4. **indicators/indicators.py**: Technical analysis
   - Calculates EMA (Exponential Moving Average)
   - Calculates Supertrend indicator
   - Calculates ATR (Average True Range)

5. **broker/execution.py**: Order management
   - Places market orders
   - Places stop orders
   - Manages positions
   - Cancels orders

6. **risk/risk_manager.py**: Risk management
   - Calculates position sizes
   - Determines stop loss levels
   - Validates trade entries

7. **strategies/strategy.py**: Trading logic
   - Implements Supertrend + EMA strategy
   - Buy: Supertrend bullish + price > EMA
   - Sell: Supertrend bearish + price < EMA

8. **portfolio/portfolio_tracker.py**: Trade tracking
   - Records all trades to CSV
   - Maintains trade history
   - Portfolio management

9. **main.py**: Orchestration
   - Initializes all modules
   - Manages trading schedule
   - Runs strategy loop
   - Closes positions at end of day

## 🔧 Configuration

Edit `config.py` to customize:

```python
# Tickers to trade
LIST_OF_TICKERS = ["AAVE/USD", "ETH/USD", 'SOL/USD']

# Trading hours (America/New_York timezone)
START_HOUR = 7
START_MIN = 1
END_HOUR = 9
END_MIN = 35

# Risk management
STOP_PERC = 2  # Stop loss percentage

# Indicator parameters
EMA_LENGTH = 10
SUPERTREND_LENGTH = 10
ATR_LENGTH = 14
```

## ▶️ Running the Bot

```bash
python main.py
```

The bot will:
1. Load configuration and initialize modules
2. Wait for start time (7:01 AM ET)
3. Execute strategy every second
4. Close all positions at end time (9:35 AM ET)
5. Generate log file with timestamp

## 📊 Output Files

- **trades.csv**: Records all executed trades
- **orders.csv**: Records all orders
- **crypto_supertrend_ema_strategy_YYYY-MM-DD.log**: Daily log file

## 🔍 Strategy Logic

### Entry (Long):
- Daily Supertrend shows bullish signal (> 0)
- Closing price > Daily EMA
- Sufficient account balance

### Exit (Long):
- Daily Supertrend shows bearish signal (< 0)
- Closing price < Daily EMA

### Risk Management:
- Position size based on available cash
- Stop loss at 2% from entry
- Minimum quantity check before entry

## 🛠️ Customization

### Adding New Indicators

Edit `indicators/indicators.py`:

```python
def add_indicators(self, df):
    df['ema'] = ta.ema(df['close'], length=self.ema_length)
    df['rsi'] = ta.rsi(df['close'], length=14)  # Add RSI
    # Add more indicators...
    return df
```

### Modifying Strategy

Edit `strategies/strategy.py`:

```python
def check_buy_condition(self, hist_df_hourly, hist_df_daily):
    buy_condition = (
        hist_df_hourly['super'].iloc[-1] > 0 and 
        hist_df_daily['ema'].iloc[-1] < hist_df_hourly['close'].iloc[-1]
        # Add your conditions here
    )
    return buy_condition
```

### Adding New Tickers

Edit `config.py`:

```python
LIST_OF_TICKERS = ["AAVE/USD", "ETH/USD", "SOL/USD", "BTC/USD"]
```

## ⚠️ Important Notes

1. **Paper Trading**: Bot uses Alpaca paper trading by default
2. **Time Zone**: All times are in America/New_York timezone
3. **Data Frequency**: Strategy runs every second
4. **Position Limits**: Checks minimum quantity before entering
5. **Stop Orders**: Automatically placed after position entry

## 🐛 Troubleshooting

### Import Errors
Ensure all `__init__.py` files exist in subdirectories.

### API Connection Issues
- Check `.env` file has correct credentials
- Verify Alpaca API keys are valid
- Check internet connection

### Data Fetch Errors
- Verify ticker symbols are correct
- Check Alpaca API status
- Ensure sufficient historical data available

## 📝 Advantages of Modular Structure

✅ **Maintainability**: Easy to update individual components
✅ **Testability**: Each module can be tested independently
✅ **Reusability**: Modules can be reused in other projects
✅ **Scalability**: Easy to add new strategies or features
✅ **Readability**: Clear separation of concerns
✅ **Debugging**: Easier to locate and fix issues

## 📚 Dependencies

```
alpaca-py
pandas
pandas-ta
pendulum
python-dotenv
```

## 🔐 Security

- Never commit `.env` file to version control
- Keep API keys secure
- Use paper trading for testing
- Review all trades before live deployment

## 📞 Support

For issues or questions:
- Check log files for errors
- Review Alpaca API documentation
- Verify configuration settings