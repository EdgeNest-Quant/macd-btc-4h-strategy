FROM python:3.11-slim-bullseye

# Set working directory
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

# Copy the entire project (preserves package structure)
COPY . .

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Expose port for Streamlit (optional)
EXPOSE 8501

# Run the bot
CMD ["python", "-m", "trading_bot.main"]

# FROM python:3.11-slim-bullseye

# WORKDIR /app

# # Install system dependencies
# RUN apt-get update && \
#     apt-get install -y --no-install-recommends \
#     gcc \
#     g++ \
#     make \
#     python3-dev \
#     && rm -rf /var/lib/apt/lists/*

# # Copy requirements and install
# COPY requirements.txt .
# RUN pip install --no-cache-dir -r requirements.txt

# # Copy the entire package
# COPY trading_bot/ ./trading_bot/

# # Set environment variables
# ENV PYTHONUNBUFFERED=1

# # Run as a module
# CMD ["python", "-m", "trading_bot"]