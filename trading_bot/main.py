"""
Main entry point for the Drift Protocol trading bot
"""
import asyncio
import signal
import sys
from datetime import datetime, timedelta
from .config import (
    TIME_ZONE, PRIVATE_KEY, SUB_ACCOUNT_ID, STRATEGY_CHECK_INTERVAL, TIMEZONE
)

from .logger import logger, setup_logger
from .data.data_handler import DriftDataHandler
from .broker.execution import DriftOrderExecutor
from .risk.risk_manager import DriftRiskManager
from .portfolio.portfolio_tracker import DriftPortfolioTracker
from .strategies.macd_strategy_btc_4h_advanced import DriftMACDStrategy


class DriftTradingBot:
    def __init__(self):
        """Initialize the Drift trading bot"""
        self.running = False
        self.strategy = None
        self.data_handler = None
        self.order_executor = None
        self.risk_manager = None
        self.portfolio_tracker = None
        
    async def initialize(self):
        """Initialize all bot components"""
        try:
            logger.info("Initializing Drift Protocol Trading Bot...")
            
            # Validate required configuration
            if not PRIVATE_KEY:
                raise ValueError("PRIVATE_KEY must be set in environment variables or .env file")
            
            # Initialize all modules
            self.data_handler = DriftDataHandler()
            self.order_executor = DriftOrderExecutor(PRIVATE_KEY, SUB_ACCOUNT_ID)
            self.risk_manager = DriftRiskManager()
            self.portfolio_tracker = DriftPortfolioTracker()
            
            # Initialize strategy
            self.strategy = DriftMACDStrategy(
                self.data_handler,
                self.order_executor,
                self.risk_manager,
                self.portfolio_tracker
            )
            
            # Initialize all async components
            await self.strategy.initialize()
            
            logger.info("All components initialized successfully")
            
            # Print current portfolio (with error handling)
            try:
                self.portfolio_tracker.print_trades(days=7)  # Show last 7 days
            except Exception as e:
                logger.warning(f"Error printing portfolio history: {e}")
                print("No trades in current session")
            
        except Exception as e:
            logger.error(f"Failed to initialize bot: {e}")
            raise
    
    def setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown"""
        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}, initiating shutdown...")
            self.running = False
            
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    
    async def run_trading_loop(self):
        """Main trading loop - runs 24/7 for crypto markets"""
        try:
            if not self.running:
                return
            
            now = datetime.now(TIMEZONE)
            logger.info(f"Current time: {now}")
            logger.info("Starting 24/7 trading loop...")
            logger.info("Strategy execution begins!")
            
            last_run = datetime.now(TIMEZONE)
            
            while self.running:
                now = datetime.now(TIMEZONE)
                
                # Check if it's time to run strategy
                time_since_last_run = (now - last_run).total_seconds()
                
                if time_since_last_run >= STRATEGY_CHECK_INTERVAL:
                    logger.debug(f"Running strategy at {now}")
                    
                    try:
                        await self.strategy.run_strategy()
                        last_run = now
                        
                        # Print session summary periodically
                        if now.minute % 15 == 0 and now.second == 0:  # Every 15 minutes
                            self.portfolio_tracker.print_session_summary()
                            
                    except Exception as e:
                        logger.error(f"Error in strategy execution: {e}")
                        await asyncio.sleep(5)  # Brief pause before continuing
                
                await asyncio.sleep(1)  # Check every second
                
        except Exception as e:
            logger.error(f"Error in trading loop: {e}")
        finally:
            logger.info("Trading loop ended")
    
    async def shutdown(self):
        """Graceful shutdown"""
        logger.info("Shutting down trading bot...")
        
        try:
            if self.strategy:
                await self.strategy.close_all_positions()
                await self.strategy.cleanup()
            
            # Print final session summary
            if self.portfolio_tracker:
                self.portfolio_tracker.print_session_summary()
                logger.info("Final portfolio state:")
                self.portfolio_tracker.print_trades(days=1)
            
            logger.info("Shutdown completed successfully")
            
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")
    
    async def run(self):
        """Main bot execution"""
        self.running = True
        self.setup_signal_handlers()
        
        try:
            await self.initialize()
            await self.run_trading_loop()
        except KeyboardInterrupt:
            logger.info("Interrupted by user")
        except Exception as e:
            logger.error(f"Bot execution error: {e}")
        finally:
            await self.shutdown()


async def main():
    """Main async entry point"""
    # Setup logging
    setup_logger()
    
    # Create and run bot
    bot = DriftTradingBot()
    await bot.run()


def sync_main():
    """Synchronous entry point for backwards compatibility"""
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    sync_main()