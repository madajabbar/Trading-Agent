# 🤖 Agent Bot Trading

An intelligent cryptocurrency trading bot that combines technical analysis with AI-powered market sentiment analysis for automated futures trading on Bybit.

## 🚀 Features

- **Multi-Strategy Trading**: Implements both Trend Following and Mean Reversion strategies
- **AI-Powered Analysis**: Uses Google Gemini AI for market sentiment analysis
- **Risk Management**: Advanced stop-loss and take-profit mechanisms based on ATR
- **Real-time Dashboard**: Live monitoring via Streamlit web interface
- **Parallel Processing**: Concurrent analysis of multiple trading pairs
- **Adaptive Strategy Selection**: Automatically chooses strategy based on market conditions
- **Position Management**: Comprehensive tracking of open positions and PnL

## 📊 Trading Strategies

### 1. Trend Following Strategy
- **Timeframe**: 4-hour trend analysis with 1-hour entry signals
- **Indicators**: SMA(50), RSI(14), MACD
- **Entry Conditions**: 
  - LONG: Price > SMA(50), RSI < 40, MACD bullish cross
  - SHORT: Price < SMA(50), RSI > 60, MACD bearish cross

### 2. Mean Reversion Strategy
- **Timeframe**: 15-minute analysis
- **Indicators**: Bollinger Bands
- **Entry Conditions**:
  - LONG: Price touches lower Bollinger Band
  - SHORT: Price touches upper Bollinger Band

### 3. Adaptive Strategy Selection
- **ADX-based**: Automatically selects strategy based on market volatility
  - ADX > 25: Trending market → Trend Following
  - ADX < 20: Sideways market → Mean Reversion
  - ADX 20-25: Unclear conditions → Hold

## 🛡️ Risk Management

- **Dynamic Stop Loss**: Based on ATR (Average True Range)
- **Take Profit**: Risk/Reward ratio of 1:2
- **Position Sizing**: Configurable margin allocation per trade
- **Leverage Control**: Adjustable leverage settings
- **Trailing Stop Loss**: Optional trailing stop mechanism

## 📋 Prerequisites

- Python 3.8 or higher
- Bybit account with API access
- Google Gemini AI API key
- Windows/Linux/macOS

## 🛠️ Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd agent-bot-trading
   ```

2. **Create virtual environment**
   ```bash
   python -m venv env
   
   # Windows
   env\Scripts\activate
   
   # Linux/macOS
   source env/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Install TA-Lib** (if not automatically installed)
   - **Windows**: Download from [TA-Lib releases](https://github.com/TA-Lib/ta-lib-python/releases)
   - **Linux**: `sudo apt-get install ta-lib`
   - **macOS**: `brew install ta-lib`

5. **Configure environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your API keys
   ```

## ⚙️ Configuration

### Required API Keys

1. **Bybit API**:
   - Visit [Bybit API Management](https://www.bybit.com/app/user/api-management)
   - Create new API key with futures trading permissions
   - Add to `.env` file

2. **Google Gemini AI**:
   - Visit [Google AI Studio](https://aistudio.google.com/app/apikey)
   - Generate API key
   - Add to `.env` file

### Environment Variables

```env
# Required
BYBIT_API_KEY=your_bybit_api_key_here
BYBIT_API_SECRET=your_bybit_api_secret_here
GEMINI_API_KEY=your_gemini_api_key_here

# Optional (defaults provided)
MARGIN_BALANCE=10.0
LEVERAGE=5
ATR_SL_MULTIPLIER=2.0
ATR_TP_MULTIPLIER=4.0
TRAILING_STOP_LOSS_PERCENT=5.0
```

## 🚀 Usage

### Running the Main Trading Bot

```bash
python main.py
```

This will start the main trading loop with:
- Automatic strategy selection
- Parallel analysis of multiple trading pairs
- Real-time position management
- Live data persistence

### Running the Dashboard

```bash
streamlit run dashboard.py
```

Access the dashboard at `http://localhost:8501` to monitor:
- Current positions and PnL
- Trading history
- Real-time balance updates
- Performance metrics

### Running Specific Strategies

```bash
# Mean Reversion Strategy
python backtester.py

# Legacy Trading Agent
python trading_agent.py
```

## 📁 Project Structure

```
agent-bot-trading/
├── main.py              # Main trading loop with adaptive strategy
├── strategy.py          # Trading strategy implementations
├── api_clients.py       # Bybit and Gemini API interactions
├── config.py           # Configuration and API setup
├── dashboard.py        # Streamlit web dashboard
├── backtester.py       # Backtesting framework
├── trading_agent.py    # Legacy trading agent
├── requirements.txt    # Python dependencies
├── .env.example       # Environment variables template
└── README.md          # This file
```

## 📊 Data Files

- `live_data.json`: Real-time trading state and positions
- `trading_log.csv`: Historical trading records
- `*_data.csv`: Historical market data files

## ⚠️ Important Notes

### Risk Disclaimer
- **This is for educational purposes only**
- **Never trade with money you cannot afford to lose**
- **Test thoroughly on paper trading first**
- **Cryptocurrency trading involves significant risk**

### API Security
- Never share your API keys
- Use API keys with minimal required permissions
- Consider using testnet for initial testing
- Monitor API usage and rate limits

### Performance Considerations
- The bot uses parallel processing for efficiency
- API rate limits are respected with delays
- Historical data is cached to reduce API calls
- Monitor system resources during operation

## 🔧 Customization

### Adding New Strategies

1. Create a new decision function in `strategy.py`
2. Add the strategy to `make_adaptive_decision()`
3. Test with historical data using `backtester.py`

### Modifying Risk Parameters

Edit the global variables in `main.py`:
```python
ATR_SL_MULTIPLIER = 2.0    # Stop-loss distance
ATR_TP_MULTIPLIER = 4.0    # Take-profit distance
LEVERAGE = 5               # Trading leverage
MARGIN_BALANCE = 10.0      # Starting balance
```

### Dashboard Customization

Modify `dashboard.py` to add:
- Additional metrics
- Custom charts
- Alert notifications
- Export functionality

## 🐛 Troubleshooting

### Common Issues

1. **TA-Lib Installation Error**:
   ```bash
   pip install --upgrade setuptools wheel
   pip install TA-Lib
   ```

2. **API Connection Issues**:
   - Verify API keys are correct
   - Check internet connection
   - Ensure API permissions are enabled

3. **Memory Issues**:
   - Reduce `INITIAL_CANDIDATES` in `strategy.py`
   - Decrease `limit` parameter in API calls
   - Restart the application periodically

4. **Dashboard Not Loading**:
   - Ensure Streamlit is installed: `pip install streamlit`
   - Check if port 8501 is available
   - Verify `live_data.json` exists

## 📈 Performance Monitoring

The bot provides several ways to monitor performance:

1. **Console Output**: Real-time trading decisions and results
2. **Dashboard**: Visual interface with metrics and charts
3. **Log Files**: Detailed CSV records of all trades
4. **JSON State**: Persistent storage of current positions

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## 📄 License

This project is for educational purposes only. Use at your own risk.

## 🔗 Useful Links

- [Bybit API Documentation](https://bybit-exchange.github.io/docs/)
- [Google Gemini AI Documentation](https://ai.google.dev/docs)
- [TA-Lib Documentation](https://ta-lib.org/)
- [Streamlit Documentation](https://docs.streamlit.io/)

---

**⚠️ Remember: Always test your strategies thoroughly before live trading!**
