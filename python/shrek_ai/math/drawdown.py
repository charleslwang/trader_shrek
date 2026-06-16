"""
Drawdown and trailing stop calculations
"""

from typing import Optional
import numpy as np
from loguru import logger


def drawdown(current_price: float, peak_price: float) -> float:
    """
    Calculate drawdown from peak.
    
    Args:
        current_price: Current price
        peak_price: Peak price
    
    Returns:
        Drawdown (0 to 1)
    """
    if peak_price <= 0:
        return 0.0
    
    ratio = current_price / peak_price
    if ratio < 1:
        return 1 - ratio
    return 0.0


def max_drawdown(prices: list[float]) -> float:
    """
    Calculate maximum drawdown from a series of prices.
    
    Args:
        prices: List of prices
    
    Returns:
        Maximum drawdown (0 to 1)
    """
    if not prices:
        return 0.0
    
    peak = prices[0]
    max_dd = 0.0
    
    for price in prices[1:]:
        if price > peak:
            peak = price
        else:
            dd = drawdown(price, peak)
            if dd > max_dd:
                max_dd = dd
    
    return max_dd


def drawdown_quantile(drawdowns: list[float], quantile: float = 0.85) -> float:
    """
    Calculate drawdown quantile from historical drawdowns.
    
    Args:
        drawdowns: List of historical drawdowns
        quantile: Quantile to calculate (default 0.85)
    
    Returns:
        Drawdown at quantile
    """
    if not drawdowns:
        return 0.0
    
    sorted_dd = sorted(drawdowns)
    index = int((len(sorted_dd) - 1) * quantile)
    return sorted_dd[index]


def drawdown_stop_price(entry_price: float, drawdown_threshold: float) -> float:
    """
    Calculate stop price based on drawdown threshold.
    
    Args:
        entry_price: Entry price
        drawdown_threshold: Drawdown threshold (0 to 1)
    
    Returns:
        Stop price
    """
    return entry_price * (1 - drawdown_threshold)


def running_high(prices: list[float], start_index: int = 0) -> list[float]:
    """
    Calculate running high from a series of prices.
    
    Args:
        prices: List of prices
        start_index: Starting index
    
    Returns:
        List of running highs
    """
    if not prices:
        return []
    
    running_highs = []
    current_high = prices[start_index]
    
    for price in prices[start_index:]:
        if price > current_high:
            current_high = price
        running_highs.append(current_high)
    
    return running_highs


def high_52w(prices: list[float]) -> Optional[float]:
    """
    Calculate 52-week high.
    
    Args:
        prices: List of daily prices (at least 252 data points)
    
    Returns:
        52-week high or None if insufficient data
    """
    if len(prices) < 252:
        return None
    
    return max(prices[-252:])


def drawdown_52w(current_price: float, prices: list[float]) -> Optional[float]:
    """
    Calculate drawdown from 52-week high.
    
    Args:
        current_price: Current price
        prices: List of daily prices
    
    Returns:
        Drawdown from 52-week high or None if insufficient data
    """
    high = high_52w(prices)
    if high is None:
        return None
    
    return drawdown(current_price, high)


def trailing_stop_price(
    current_price: float,
    running_high: float,
    atr: float,
    atr_multiplier: float = 2.5,
    min_threshold: float = 0.15,
) -> float:
    """
    Calculate trailing stop price.
    
    Args:
        current_price: Current price
        running_high: Running high since entry
        atr: Average true range
        atr_multiplier: ATR multiplier
        min_threshold: Minimum trailing threshold
    
    Returns:
        Trailing stop price
    """
    # Calculate ATR-based threshold
    atr_threshold = (atr * atr_multiplier) / current_price
    threshold = max(atr_threshold, min_threshold)
    
    return running_high * (1 - threshold)


def trailing_drawdown(current_price: float, running_high: float) -> float:
    """
    Calculate trailing drawdown from running high.
    
    Args:
        current_price: Current price
        running_high: Running high since entry
    
    Returns:
        Trailing drawdown (0 to 1)
    """
    if running_high <= 0:
        return 0.0
    
    return 1 - (current_price / running_high)


def is_trailing_stop_triggered(
    current_price: float,
    running_high: float,
    trailing_threshold: float,
) -> bool:
    """
    Check if trailing stop is triggered.
    
    Args:
        current_price: Current price
        running_high: Running high since entry
        trailing_threshold: Trailing threshold (0 to 1)
    
    Returns:
        Whether trailing stop is triggered
    """
    dd = trailing_drawdown(current_price, running_high)
    return dd >= trailing_threshold


def should_activate_trailing(
    current_price: float,
    entry_price: float,
    activation_gain: float = 0.30,
) -> bool:
    """
    Check if trailing stop should be activated.
    
    Args:
        current_price: Current price
        entry_price: Entry price
        activation_gain: Gain threshold for activation
    
    Returns:
        Whether trailing stop should be activated
    """
    if entry_price <= 0:
        return False
    
    gain = (current_price / entry_price) - 1
    return gain >= activation_gain


def gain_from_entry(current_price: float, entry_price: float) -> float:
    """
    Calculate gain from entry.
    
    Args:
        current_price: Current price
        entry_price: Entry price
    
    Returns:
        Gain (0 to 1)
    """
    if entry_price <= 0:
        return 0.0
    
    return (current_price / entry_price) - 1
