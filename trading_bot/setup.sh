#!/bin/bash

# Drift Protocol Trading Bot Setup Script
# Sets up a Python virtual environment and installs all dependencies

set -e

echo "🚀 Setting up Drift Protocol Trading Bot..."
echo ""

# Check Python version
PYTHON_CMD=""
for cmd in python3.11 python3 python; do
    if command -v "$cmd" &>/dev/null; then
        PYTHON_CMD="$cmd"
        break
    fi
done

if [ -z "$PYTHON_CMD" ]; then
    echo "❌ Python 3 not found. Please install Python 3.11+."
    exit 1
fi

echo "Using Python: $($PYTHON_CMD --version)"

# Navigate to project root (parent of trading_bot/)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

echo "📁 Project root: $PROJECT_ROOT"

# Create virtual environment
if [ ! -d ".venv" ]; then
    echo "📦 Creating virtual environment..."
    $PYTHON_CMD -m venv .venv
fi

echo "🔗 Activating virtual environment..."
source .venv/bin/activate

echo "📥 Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Check for .env file
if [ ! -f ".env" ]; then
    echo ""
    echo "🔐 Creating .env template..."
    cat > .env << 'EOF'
# Solana & Drift Configuration
PRIVATE_KEY=your_base58_private_key_here
SOLANA_RPC_URL=https://api.devnet.solana.com
RPC_URL=https://devnet.helius-rpc.com/?api-key=YOUR_KEY_HERE
DRIFT_ENV=devnet
EOF
    echo "⚠️  Edit .env with your actual credentials before running the bot."
else
    echo "✅ .env already exists"
fi

# Create data directory
mkdir -p data logs

echo ""
echo "✨ Setup complete!"
echo ""
echo "📌 Next steps:"
echo "1. Edit .env with your Solana private key and RPC URL"
echo "2. Activate the venv: source .venv/bin/activate"
echo "3. Run the bot: python -m trading_bot.main"
echo ""
echo "Happy trading! 🎯"