#!/bin/bash

# Step-by-step installation script for Drift Protocol Trading Bot
# Run this if pip install -r requirements.txt fails due to dependency conflicts

echo "🔧 Installing Drift Protocol Trading Bot - Step by Step"
echo "=================================================="

# Update pip first
echo "📦 Updating pip..."
pip install --upgrade pip

# Step 1: Install core numerical libraries first
echo ""
echo "📊 Step 1: Installing core numerical libraries..."
pip install numpy==1.26.4

# Step 2: Install pandas (depends on numpy)
echo ""
echo "📈 Step 2: Installing pandas..."
pip install pandas==2.2.3

# Step 3: Install basic utilities
echo ""
echo "🛠️  Step 3: Installing utilities..."
pip install python-dotenv==1.0.1 requests==2.32.3 pendulum==3.0.0

# Step 4: Install websockets
echo ""
echo "🌐 Step 4: Installing websockets..."
pip install websockets==13.1

# Step 5: Install Solana libraries
echo ""
echo "⚡ Step 5: Installing Solana libraries..."
pip install solders==0.21.0

# Step 6: Install Anchor and Drift
echo ""
echo "🚀 Step 6: Installing Drift Protocol SDK..."
pip install anchorpy==0.20.1
pip install driftpy==0.8.76

# Optional: Install technical analysis (may cause conflicts)
echo ""
echo "📊 Step 7: Installing technical analysis (optional)..."
echo "⚠️  Note: pandas-ta may cause conflicts. The bot uses custom indicators instead."
# pip install pandas-ta==0.3.14b0

echo ""
echo "✅ Installation complete!"
echo ""
echo "Next steps:"
echo "1. Copy .env.example to .env"
echo "2. Add your private key to .env"
echo "3. Test with: python test_integration.py"
echo "4. Run bot with: python -m dex_trading_bot.main"
echo ""