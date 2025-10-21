


"""
Logging configuration for the Drift Protocol trading bot
"""
import logging
import sys
from datetime import datetime
from pathlib import Path
from .config import STRATEGY_NAME, DEBUG, TIMEZONE


def setup_logger(name: str = None, level: str = None) -> logging.Logger:
    """
    Set up and configure the logger with both file and console handlers
    
    Args:
        name: Logger name (defaults to STRATEGY_NAME)
        level: Logging level (defaults to DEBUG if DEBUG=True, else INFO)
    
    Returns:
        Configured logger instance
    """
    logger_name = name or STRATEGY_NAME
    log_level = level or (logging.DEBUG if DEBUG else logging.INFO)
    
    # Create logs directory if it doesn't exist
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)
    
    # Generate log filename with timestamp
    timestamp = datetime.now(TIMEZONE).strftime("%Y%m%d")
    log_filename = logs_dir / f'{logger_name}_{timestamp}.log'
    
    # Get or create logger
    logger = logging.getLogger(logger_name)
    logger.setLevel(log_level)
    
    # Clear existing handlers to avoid duplicates
    logger.handlers.clear()
    
    # Create formatter
    formatter = logging.Formatter(
        "%(asctime)s UTC - %(levelname)8s - %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    # File handler - always INFO level minimum for persistence
    file_handler = logging.FileHandler(log_filename, mode='a', encoding='utf-8')
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    # Console handler - respects debug setting
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # Suppress overly verbose third-party loggers
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("websockets").setLevel(logging.WARNING)
    logging.getLogger("solders").setLevel(logging.WARNING)
    logging.getLogger("solana").setLevel(logging.WARNING)
    
    logger.info(f"Logger initialized: {logger_name}")
    logger.info(f"Log file: {log_filename}")
    logger.info(f"Log level: {logging.getLevelName(log_level)}")
    
    return logger


# Create default logger instance
logger = setup_logger()
