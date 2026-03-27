FROM python:3.11-slim-bullseye

WORKDIR /app

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    make \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy only what the bot needs
COPY trading_bot/ ./trading_bot/
COPY data/ ./data/
COPY trades.csv* ./

ENV PYTHONUNBUFFERED=1

# Run the bot
CMD ["python", "-m", "trading_bot.main"]