#!/bin/bash

# Drift Protocol Trading Bot Dashboard - Startup Script

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

echo "🚀 Drift Protocol Trading Bot Dashboard"
echo "========================================"
echo ""

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo "❌ Error: Python 3 is not installed"
    exit 1
fi

echo "✅ Python found: $(python3 --version)"
echo ""

# Check if .env file exists
if [ ! -f "../.env" ]; then
    echo "⚠️  Warning: ../.env file not found"
    echo "Please ensure PRIVATE_KEY and SOLANA_RPC_URL are set"
    echo ""
fi

# Check if trades.csv exists
if [ ! -f "../trades.csv" ]; then
    echo "⚠️  Warning: ../trades.csv not found"
    echo "Dashboard will show empty data until trades execute"
    echo ""
fi

# Install dependencies if needed
if ! pip list | grep -q streamlit; then
    echo "📦 Installing dependencies..."
    pip install -r requirements.txt
    echo "✅ Dependencies installed"
    echo ""
fi

# Display startup info
echo "📊 Starting Streamlit Dashboard..."
echo ""
echo "Local URL:      http://localhost:8501"
echo "Network URL:    http://$(hostname -I | awk '{print $1}'):8501"
echo ""
echo "Press Ctrl+C to stop"
echo "========================================"
echo ""

# Start Streamlit
streamlit run app.py --logger.level=warning
