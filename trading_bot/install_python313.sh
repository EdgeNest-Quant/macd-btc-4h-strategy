#!/bin/bash

# Drift Protocol Bot Installation Script for Python 3.13
# This script handles dependency conflicts and Python 3.13 compatibility

echo "🚀 Installing Drift Protocol Trading Bot Dependencies..."
echo "Python version: $(python --version)"

# Upgrade pip first
echo "📦 Upgrading pip..."
pip install --upgrade pip

# Install core dependencies first
echo "📦 Installing core dependencies..."
pip install numpy==1.26.4 pandas==2.2.3 python-dotenv==1.0.1 requests==2.32.3

# Install date/time and networking
echo "📦 Installing additional utilities..."
pip install pendulum==3.0.0 websockets==13.0

# Fix cffi for Python 3.13
echo "📦 Installing Python 3.13 compatible cffi..."
pip install cffi>=1.16.0

# Install driftpy with no dependencies first, then let it resolve
echo "📦 Installing Drift Protocol SDK..."
pip install --no-deps driftpy==0.8.76
pip install anchorpy==0.21.0

# Now install driftpy dependencies that aren't conflicting
echo "📦 Resolving remaining driftpy dependencies..."
pip install solders aiohttp aiosignal anyio attrs backoff base58 \
    construct construct-typing deprecated loguru pynacl solana \
    typing-extensions yarl tqdm

echo "✅ Installation complete!"
echo ""
echo "🧪 Testing imports..."
python -c "
try:
    import numpy as np
    print('✅ numpy imported successfully')
    import pandas as pd
    print('✅ pandas imported successfully')
    import driftpy
    print('✅ driftpy imported successfully')
    print('🎉 All critical imports working!')
except ImportError as e:
    print(f'❌ Import error: {e}')
    print('Some packages may need manual installation')
"

echo ""
echo "🚀 Ready to run your Drift Protocol trading bot!"
echo "Try: python main.py"