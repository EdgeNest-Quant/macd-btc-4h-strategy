# import pandas_ta as ta

# def add_indicators(df):
#     """
#     Add all technical indicators used in the strategy to the dataframe.
#     """
#     df["ema"] = ta.ema(df["close"], length=10)
#     df["super"] = ta.supertrend(
#         df.high, df.low, df.close, length=10)["SUPERTd_10_3.0"]
#     df["atr"] = ta.atr(df.high, df.low, df.close, length=14)
#     return df



"""
Technical indicators calculation - Custom implementation
No external TA library dependencies to avoid conflicts
"""
import pandas as pd
import numpy as np
from ..logger import logger

# Legacy indicator defaults (not used by MACD strategy)
EMA_LENGTH = 10
SUPERTREND_LENGTH = 10
ATR_LENGTH = 14


class IndicatorCalculator:
    def __init__(self):
        """Initialize the indicator calculator"""
        self.ema_length = EMA_LENGTH
        self.supertrend_length = SUPERTREND_LENGTH
        self.atr_length = ATR_LENGTH
    
    def calculate_ema(self, series, length):
        """Calculate Exponential Moving Average"""
        return series.ewm(span=length, adjust=False).mean()
    
    def calculate_atr(self, high, low, close, length):
        """Calculate Average True Range"""
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        
        true_range = pd.DataFrame({'tr1': tr1, 'tr2': tr2, 'tr3': tr3}).max(axis=1)
        atr = true_range.rolling(window=length).mean()
        
        return atr
    
    def calculate_supertrend(self, high, low, close, length=10, multiplier=3.0):
        """
        Calculate Supertrend indicator
        Returns 1 for bullish, -1 for bearish, 0 for neutral
        """
        try:
            # Calculate ATR for Supertrend
            atr = self.calculate_atr(high, low, close, length)
            
            # Calculate basic upper and lower bands
            hl2 = (high + low) / 2
            upper_band = hl2 + (multiplier * atr)
            lower_band = hl2 - (multiplier * atr)
            
            # Initialize supertrend
            supertrend = pd.Series(index=close.index, dtype=float)
            direction = pd.Series(index=close.index, dtype=int)
            
            # Calculate supertrend
            for i in range(1, len(close)):
                if pd.isna(atr.iloc[i]):
                    supertrend.iloc[i] = 0
                    direction.iloc[i] = 0
                    continue
                
                # Current close price
                curr_close = close.iloc[i]
                prev_close = close.iloc[i-1] if i > 0 else curr_close
                
                # Adjust bands based on previous values
                if i > 0:
                    if upper_band.iloc[i] < upper_band.iloc[i-1] or prev_close > upper_band.iloc[i-1]:
                        upper_band.iloc[i] = upper_band.iloc[i]
                    else:
                        upper_band.iloc[i] = upper_band.iloc[i-1]
                    
                    if lower_band.iloc[i] > lower_band.iloc[i-1] or prev_close < lower_band.iloc[i-1]:
                        lower_band.iloc[i] = lower_band.iloc[i]
                    else:
                        lower_band.iloc[i] = lower_band.iloc[i-1]
                
                # Determine trend direction
                if i == 0:
                    direction.iloc[i] = 1  # Start bullish
                else:
                    if direction.iloc[i-1] == 1:
                        direction.iloc[i] = -1 if curr_close <= lower_band.iloc[i] else 1
                    else:
                        direction.iloc[i] = 1 if curr_close >= upper_band.iloc[i] else -1
                
                # Set supertrend value
                if direction.iloc[i] == 1:
                    supertrend.iloc[i] = lower_band.iloc[i]
                else:
                    supertrend.iloc[i] = upper_band.iloc[i]
            
            # Convert to signal format: 1 for bullish, -1 for bearish
            supertrend_signal = pd.Series(index=close.index, dtype=int)
            for i in range(len(close)):
                if pd.isna(supertrend.iloc[i]) or supertrend.iloc[i] == 0:
                    supertrend_signal.iloc[i] = 0
                elif close.iloc[i] > supertrend.iloc[i]:
                    supertrend_signal.iloc[i] = 1  # Bullish
                else:
                    supertrend_signal.iloc[i] = -1  # Bearish
            
            return supertrend_signal
            
        except Exception as e:
            logger.error(f"Error calculating Supertrend: {e}")
            # Return neutral signal on error
            return pd.Series([0] * len(close), index=close.index)
    
    def add_indicators(self, df):
        """
        Add EMA, Supertrend, and ATR indicators to dataframe
        """
        try:
            if df.empty or len(df) < max(self.ema_length, self.supertrend_length, self.atr_length):
                logger.warning("Insufficient data for indicator calculation")
                df['ema'] = 0
                df['super'] = 0
                df['atr'] = 0
                return df
            
            # Calculate EMA
            df['ema'] = self.calculate_ema(df['close'], self.ema_length)
            
            # Calculate ATR
            df['atr'] = self.calculate_atr(df['high'], df['low'], df['close'], self.atr_length)
            
            # Calculate Supertrend
            df['super'] = self.calculate_supertrend(
                df['high'], 
                df['low'], 
                df['close'], 
                self.supertrend_length
            )
            
            # Fill NaN values with 0
            df['ema'] = df['ema'].fillna(0)
            df['atr'] = df['atr'].fillna(0)
            df['super'] = df['super'].fillna(0)
            
            logger.debug(f"Indicators calculated: EMA={df['ema'].iloc[-1]:.4f}, "
                        f"ATR={df['atr'].iloc[-1]:.4f}, Super={df['super'].iloc[-1]}")
            
            return df
            
        except Exception as e:
            logger.error(f"Error adding indicators: {e}")
            # Return dataframe with zero indicators on error
            df['ema'] = 0
            df['super'] = 0
            df['atr'] = 0
            return df
