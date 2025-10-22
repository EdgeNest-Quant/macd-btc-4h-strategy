"""
Risk management module for Drift Protocol trading
"""
from ..config import MAX_POSITION_PCT, CASH_ALLOCATION_MODE, SAFETY_MARGIN
from ..logger import logger


class DriftRiskManager:
    def __init__(self):
        """Initialize the Drift risk manager"""
        self.stop_percentage = 2  # Legacy 2% stop (not used by MACD strategy)
        self.safety_margin = SAFETY_MARGIN
        self.max_position_pct = MAX_POSITION_PCT
        self.cash_allocation_mode = CASH_ALLOCATION_MODE
        
    def calculate_position_size(self, available_cash: float, price: float, num_positions: int = 1) -> float:
        """
        Calculate position size based on available cash and risk parameters
        
        Args:
            available_cash: Available USDC balance
            price: Asset price
            num_positions: Number of positions to allocate across
            
        Returns:
            Position size in base asset units
        """
        if price <= 0 or available_cash <= 0:
            return 0.0
            
        try:
            # Apply safety margin
            usable_cash = available_cash * self.safety_margin
            
            # Cap by maximum position percentage
            max_trade_cash = usable_cash * self.max_position_pct
            
            logger.debug(f"[RiskManager] Config: MAX_POSITION_PCT={self.max_position_pct}, SAFETY_MARGIN={self.safety_margin}")
            logger.debug(f"[RiskManager] Calculations: available=${available_cash:.2f}, usable=${usable_cash:.2f}, max_trade=${max_trade_cash:.8f}")
            
            # Allocate cash based on mode
            if self.cash_allocation_mode.lower() == "equal":
                # Split equally across all positions
                equal_split = usable_cash / max(1, num_positions)
                cash_per_position = min(max_trade_cash, equal_split)
                logger.debug(f"[RiskManager] Equal mode: max_trade_cash=${max_trade_cash:.8f}, equal_split=${equal_split:.2f}, chosen=${cash_per_position:.8f}")
            else:  # "full" mode
                cash_per_position = max_trade_cash
                logger.debug(f"[RiskManager] Full mode: cash_per_position=${cash_per_position:.8f}")
            
            # Calculate quantity
            quantity = cash_per_position / price
            
            logger.debug(f"Position sizing: Cash=${available_cash:.2f}, "
                        f"Usable=${usable_cash:.2f}, Per-position=${cash_per_position:.2f}, "
                        f"Price=${price:.4f}, Qty={quantity:.6f}")
            
            # Additional debug for the large quantity issue
            logger.info(f"[DEBUG] Position calculation - Available: ${available_cash:.2f}, "
                       f"Max%: {self.max_position_pct*100:.4f}%, Safety: {self.safety_margin*100:.0f}%, "
                       f"Price: ${price:.2f}, Final Qty: {quantity:.8f}")
            
            return quantity
            
        except Exception as e:
            logger.error(f"Error calculating position size: {e}")
            return 0.0
    
    def calculate_stop_loss(self, entry_price: float, side: str = 'long') -> float:
        """
        Calculate stop loss price based on entry price and direction
        
        Args:
            entry_price: Entry price
            side: 'long' or 'short'
            
        Returns:
            Stop loss price
        """
        try:
            if side.lower() == 'long':
                # For long positions, stop loss is below entry
                stop_price = entry_price * (1 - self.stop_percentage / 100)
            else:
                # For short positions, stop loss is above entry
                stop_price = entry_price * (1 + self.stop_percentage / 100)
            
            logger.debug(f"Stop loss calculated: Entry=${entry_price:.4f}, "
                        f"Side={side}, Stop=${stop_price:.4f} ({self.stop_percentage}%)")
            
            return stop_price
            
        except Exception as e:
            logger.error(f"Error calculating stop loss: {e}")
            return entry_price  # Return entry price as fallback
    
    def should_enter_position(self, quantity: float, min_quantity: float = 0.001) -> bool:
        """
        Check if position size meets minimum requirements
        
        Args:
            quantity: Calculated position quantity
            min_quantity: Minimum viable quantity
            
        Returns:
            True if position should be entered
        """
        should_enter = quantity >= min_quantity
        
        if not should_enter:
            logger.debug(f"Position size too small: {quantity:.6f} < {min_quantity:.6f}")
        
        return should_enter
    
    def calculate_max_leverage(self, account_value: float, position_value: float) -> float:
        """
        Calculate current leverage ratio
        
        Args:
            account_value: Total account value
            position_value: Total position value
            
        Returns:
            Current leverage ratio
        """
        if account_value <= 0:
            return 0.0
            
        leverage = position_value / account_value
        return leverage
    
    def validate_trade_size(self, quantity: float, price: float, max_trade_value: float = 10000) -> bool:
        """
        Validate if trade size is within acceptable limits
        
        Args:
            quantity: Trade quantity
            price: Trade price
            max_trade_value: Maximum trade value in USD
            
        Returns:
            True if trade size is acceptable
        """
        trade_value = quantity * price
        
        if trade_value > max_trade_value:
            logger.warning(f"Trade value ${trade_value:.2f} exceeds maximum ${max_trade_value:.2f}")
            return False
            
        return True
    
    def get_risk_metrics(self) -> dict:
        """Get current risk management configuration"""
        return {
            'stop_percentage': self.stop_percentage,
            'safety_margin': self.safety_margin,
            'max_position_pct': self.max_position_pct,
            'cash_allocation_mode': self.cash_allocation_mode
        }


# Backwards compatibility alias
RiskManager = DriftRiskManager
        
#         return stop_price
    
#     def should_enter_position(self, quantity, min_quantity=1):
#         """
#         Check if we should enter a position based on quantity
#         """
#         return quantity >= min_quantity


# trading_bot/risk/risk_manager.py


"""
Risk management module
"""
from ..config import MAX_POSITION_PCT, CASH_ALLOCATION_MODE
from ..logger import logger

# Legacy constant for backward compatibility
STOP_PERC = 2


class RiskManager:
    def __init__(self, safety_margin=0.95):
        self.safety_margin = safety_margin
    
    def calculate_position_size(self, available_cash, price, num_positions=1):
        if CASH_ALLOCATION_MODE == "equal":
            allocation = (available_cash * self.safety_margin) / num_positions
        elif CASH_ALLOCATION_MODE == "percent":
            allocation = available_cash * MAX_POSITION_PCT * self.safety_margin
        else:
            raise ValueError(f"Unknown CASH_ALLOCATION_MODE: {CASH_ALLOCATION_MODE}")
        
        quantity = allocation / price
        logger.debug(f"[RiskManager] Mode={CASH_ALLOCATION_MODE} | Cash={available_cash} | "
                     f"Price={price} | Num_Pos={num_positions} | Allocation={allocation} | "
                     f"Qty={quantity}")
        return quantity
    
    def should_enter_position(self, quantity):
        valid = quantity > 0.0001
        logger.debug(f"[RiskManager] Should enter? {valid} | Qty={quantity}")
        return valid
    
    def calculate_stop_loss(self, entry_price, side="long"):
        if side == "long":
            stop_price = entry_price * (1 - STOP_PERC / 100)
        else:
            stop_price = entry_price * (1 + STOP_PERC / 100)
        
        logger.debug(f"[RiskManager] Stop loss calc | Side={side} | Entry={entry_price} | "
                     f"Stop={stop_price}")
        return stop_price


