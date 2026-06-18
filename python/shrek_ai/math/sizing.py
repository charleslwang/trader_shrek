"""
Position sizing calculations
"""

from typing import Optional
from loguru import logger


def kelly_fraction(expected_return: float, volatility: float, risk_free_rate: float = 0.04) -> float:
    """
    Calculate Kelly fraction.
    
    Args:
        expected_return: Expected annual return (0 to 1)
        volatility: Annualized volatility (0 to 1)
        risk_free_rate: Risk-free rate (0 to 1)
    
    Returns:
        Kelly fraction
    """
    if volatility <= 0:
        logger.warning("Volatility must be positive")
        return 0.0
    
    excess_return = expected_return - risk_free_rate
    vol_squared = volatility ** 2
    
    return excess_return / vol_squared


def fractional_kelly(kelly: float, fraction: float = 0.25) -> float:
    """
    Apply fractional Kelly.
    
    Args:
        kelly: Full Kelly fraction
        fraction: Fraction to apply (default 0.25)
    
    Returns:
        Fractional Kelly
    """
    return kelly * fraction


def adjust_kelly_for_risk(
    kelly: float,
    thesis_probability: float,
    risk_penalty: float,
    upside_downside: float,
) -> float:
    """
    Adjust Kelly for confidence and risk.
    
    Args:
        kelly: Kelly fraction
        thesis_probability: Thesis probability (0 to 1)
        risk_penalty: Risk penalty (0 to 1)
        upside_downside: Upside/downside ratio
    
    Returns:
        Adjusted Kelly
    """
    confidence_factor = thesis_probability
    risk_factor = 1.0 - risk_penalty
    ud_factor = min(1.0, upside_downside / 3.0)
    
    return kelly * confidence_factor * risk_factor * ud_factor


def position_size(
    adjusted_kelly: float,
    equity: float,
    max_single_position_pct: float,
    min_order_notional: float = 1.0,
) -> float:
    """
    Calculate final position size with hard caps.
    
    Args:
        adjusted_kelly: Adjusted Kelly fraction
        equity: Total equity
        max_single_position_pct: Max position as percentage of equity
        min_order_notional: Minimum order notional
    
    Returns:
        Position notional
    """
    max_position = equity * max_single_position_pct
    kelly_position = equity * adjusted_kelly
    
    final_position = min(kelly_position, max_position)
    
    # Ensure minimum order size
    if final_position < min_order_notional:
        return 0.0
    
    return final_position


def starter_position_size(
    equity: float,
    starter_position_pct: float,
    expected_return: float,
    quality: float,
    risk_penalty: float,
    thesis_probability: float,
    upside_downside: float,
    volatility: float = 0.25,
    risk_free_rate: float = 0.04,
    kelly_scale: float = 0.25,
) -> float:
    """
    Calculate starter position size.

    Args:
        equity: Total equity
        starter_position_pct: Starter position as percentage of equity
        expected_return: Expected return
        quality: Quality score
        risk_penalty: Risk penalty
        thesis_probability: Thesis probability
        upside_downside: Upside/downside ratio
        volatility: Volatility
        risk_free_rate: Risk-free rate
        kelly_scale: Fraction of full Kelly to apply

    Returns:
        Position notional
    """
    # Calculate Kelly-based size
    full_kelly = kelly_fraction(expected_return, volatility, risk_free_rate)
    scaled_kelly = fractional_kelly(full_kelly, fraction=kelly_scale)
    adjusted = adjust_kelly_for_risk(
        scaled_kelly,
        thesis_probability,
        risk_penalty,
        upside_downside,
    )

    quality_factor = max(0.0, min(1.0, quality))
    adjusted *= quality_factor

    kelly_size = position_size(adjusted, equity, starter_position_pct)

    # Use the larger of Kelly-based or fixed starter size
    fixed_size = equity * starter_position_pct

    return max(kelly_size, fixed_size)


def add_position_size(
    equity: float,
    normal_position_pct: float,
    current_position_value: float,
    target_position_value: float,
) -> float:
    """
    Calculate add position size.
    
    Args:
        equity: Total equity
        normal_position_pct: Normal position as percentage of equity
        current_position_value: Current position value
        target_position_value: Target position value
    
    Returns:
        Add notional
    """
    max_add = equity * normal_position_pct
    needed = target_position_value - current_position_value

    if needed <= 0:
        return 0.0

    return min(needed, max_add)
