#!/bin/bash

# Drift MACD Trading Bot - Dashboard Deployment Script

echo "🚀 Deploying Drift MACD Dashboard..."
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    echo -e "${YELLOW}⚠️  Virtual environment not found. Creating...${NC}"
    python3 -m venv .venv
fi

# Activate virtual environment
echo -e "${GREEN}✅ Activating virtual environment...${NC}"
source .venv/bin/activate

# Install/upgrade dashboard dependencies
echo -e "${GREEN}📦 Installing dashboard dependencies...${NC}"
pip install --upgrade pip
pip install streamlit plotly pandas numpy

# Check if trades.csv exists
if [ ! -f "trades.csv" ]; then
    echo -e "${YELLOW}⚠️  trades.csv not found. Creating sample file...${NC}"
    echo "timestamp,symbol,market_index,market_type,side,order_type,price,quantity,fee,slippage_bps,sl,tp,pnl,unrealized_pnl,status,duration_seconds,account_equity,leverage,sub_account_id,strategy_id,signal_confidence,signal_type,tx_signature,slot,block_time,oracle_price_at_entry,execution_latency_ms,bot_version,env" > trades.csv
fi

# Launch dashboard
echo ""
echo -e "${GREEN}🎯 Launching dashboard on http://localhost:8501${NC}"
echo ""
echo -e "${YELLOW}Press Ctrl+C to stop the dashboard${NC}"
echo ""

streamlit run dashboard/app.py --server.port=8501 --server.address=localhost
