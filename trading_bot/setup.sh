#!/bin/bash

# Crypto Trading Bot Setup Script
# This script creates the complete directory structure for the modular trading bot

echo "🚀 Setting up Crypto Trading Bot..."
echo ""

# Create main directory
mkdir -p crypto_bot
cd crypto_bot

echo "📁 Creating directory structure..."

# Create subdirectories
mkdir -p data
mkdir -p indicators
mkdir -p broker
mkdir -p risk
mkdir -p strategies
mkdir -p portfolio

echo "✅ Directories created"
echo ""

echo "📝 Creating __init__.py files..."

# Create __init__.py files to make directories Python packages
touch data/__init__.py
touch indicators/__init__.py
touch broker/__init__.py
touch risk/__init__.py
touch strategies/__init__.py
touch portfolio/__init__.py

echo "✅ Package files created"
echo ""

echo "🔐 Creating .env template..."

# Create .env template
cat > .env << 'EOF'
# Alpaca API Credentials
# Replace with your actual keys
API_KEY=your_alpaca_api_key_here
SECRET_KEY=your_alpaca_secret_key_here
EOF

echo "✅ .env template created"
echo ""

echo "📋 Creating .gitignore..."

# Create .gitignore
cat > .gitignore << 'EOF'
# Environment variables
.env

# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python

# Virtual Environment
venv/
env/
ENV/

# IDE
.vscode/
.idea/
*.swp
*.swo

# Data files
*.csv
*.log

# OS
.DS_Store
Thumbs.db
EOF

echo "✅ .gitignore created"
echo ""

echo "📦 Creating requirements.txt..."

# Create requirements.txt
cat > requirements.txt << 'EOF'
alpaca-py>=0.8.0
pandas>=2.0.0
pandas-ta>=0.3.14b
pendulum>=2.1.2
python-dotenv>=1.0.0
EOF

echo "✅ requirements.txt created"
echo ""

echo "📖 Directory structure:"
tree -L 2 2>/dev/null || find . -type d -maxdepth 2

echo ""
echo "✨ Setup complete!"
echo ""
echo "📌 Next steps:"
echo "1. Copy your Python module files into their respective directories"
echo "2. Edit .env file with your Alpaca API credentials"
echo "3. Install dependencies: pip install -r requirements.txt"
echo "4. Run the bot: python main.py"
echo ""
echo "📂 File placement guide:"
echo "   config.py          → crypto_bot/"
echo "   logger.py          → crypto_bot/"
echo "   main.py            → crypto_bot/"
echo "   data_handler.py    → crypto_bot/data/"
echo "   indicators.py      → crypto_bot/indicators/"
echo "   execution.py       → crypto_bot/broker/"
echo "   risk_manager.py    → crypto_bot/risk/"
echo "   strategy.py        → crypto_bot/strategies/"
echo "   portfolio_tracker.py → crypto_bot/portfolio/"
echo ""
echo "Happy trading! 🎯"