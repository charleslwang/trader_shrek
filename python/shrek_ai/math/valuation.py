"""
Valuation models and calculations
"""

from typing import Dict, Tuple, Optional
import numpy as np
from loguru import logger


def scenario_valuation(
    bear_scenarios: Dict[str, float],
    base_scenarios: Dict[str, float],
    bull_scenarios: Dict[str, float],
    weights: Optional[Dict[str, float]] = None,
) -> Tuple[float, float, float]:
    """
    Calculate weighted valuation across three scenarios.
    
    Args:
        bear_scenarios: Valuation results for bear case
        base_scenarios: Valuation results for base case
        bull_scenarios: Valuation results for bull case
        weights: Weights for each valuation method
    
    Returns:
        Tuple of (bear_value, base_value, bull_value)
    """
    if weights is None:
        weights = {
            'dcf': 0.25,
            'ev_sales': 0.15,
            'ev_ebitda': 0.15,
            'pe': 0.15,
            'fcf_yield': 0.15,
            'peer_multiple': 0.10,
            'historical_multiple': 0.05,
        }
    
    # Filter out missing methods and renormalize weights
    available_methods = set(bear_scenarios.keys()) & set(base_scenarios.keys()) & set(bull_scenarios.keys())
    
    if not available_methods:
        logger.warning("No common valuation methods available")
        return 0.0, 0.0, 0.0
    
    # Renormalize weights for available methods
    total_weight = sum(weights.get(m, 0) for m in available_methods)
    if total_weight == 0:
        logger.warning("Total weight is zero")
        return 0.0, 0.0, 0.0
    
    normalized_weights = {m: weights.get(m, 0) / total_weight for m in available_methods}
    
    # Calculate weighted valuation for each scenario
    bear_value = sum(normalized_weights[m] * bear_scenarios[m] for m in available_methods)
    base_value = sum(normalized_weights[m] * base_scenarios[m] for m in available_methods)
    bull_value = sum(normalized_weights[m] * bull_scenarios[m] for m in available_methods)
    
    return bear_value, base_value, bull_value


def dcf_valuation(
    fcf_current: float,
    growth_rates: Tuple[float, ...],
    terminal_growth: float,
    wacc: float,
    cash: float,
    debt: float,
    preferred_equity: float,
    minority_interest: float,
    diluted_shares: float,
    projection_years: int = 5,
) -> float:
    """
    Calculate DCF-based valuation.
    
    Args:
        fcf_current: Current free cash flow
        growth_rates: Tuple of growth rates for each projection year
        terminal_growth: Terminal growth rate
        wacc: Weighted average cost of capital
        cash: Cash and cash equivalents
        debt: Total debt
        preferred_equity: Preferred equity
        minority_interest: Minority interest
        diluted_shares: Diluted shares outstanding
        projection_years: Number of projection years
    
    Returns:
        Per-share equity value
    """
    # Guardrails
    if wacc <= terminal_growth:
        logger.warning(f"WACC ({wacc}) must be greater than terminal growth ({terminal_growth})")
        return 0.0
    
    if not (0 <= terminal_growth <= 0.04):
        logger.warning(f"Terminal growth ({terminal_growth}) must be between 0% and 4%")
        return 0.0
    
    if fcf_current < 0:
        logger.warning("FCF is negative, DCF not applicable")
        return 0.0
    
    # Project FCF for each year
    fcf_projections = []
    fcf = fcf_current
    for i, g in enumerate(growth_rates[:projection_years]):
        fcf = fcf * (1 + g)
        fcf_projections.append(fcf)
    
    # Calculate present value of projected FCF
    pv_projections = sum(
        fcf / ((1 + wacc) ** (i + 1))
        for i, fcf in enumerate(fcf_projections)
    )
    
    # Calculate terminal value
    fcf_terminal = fcf_projections[-1] * (1 + terminal_growth)
    terminal_value = fcf_terminal / (wacc - terminal_growth)
    pv_terminal = terminal_value / ((1 + wacc) ** projection_years)
    
    # Calculate enterprise value
    enterprise_value = pv_projections + pv_terminal
    
    # Calculate equity value
    equity_value = enterprise_value + cash - debt - preferred_equity - minority_interest
    
    # Calculate per-share value
    if diluted_shares <= 0:
        logger.warning("Diluted shares must be positive")
        return 0.0
    
    per_share_value = equity_value / diluted_shares
    
    return per_share_value


def multiple_valuation(
    metric: float,
    multiple: float,
    cash: float,
    debt: float,
    diluted_shares: float,
) -> float:
    """
    Calculate valuation using a multiple.
    
    Args:
        metric: The metric being multiplied (e.g., revenue, EBITDA, EPS)
        multiple: The valuation multiple
        cash: Cash and cash equivalents
        debt: Total debt
        diluted_shares: Diluted shares outstanding
    
    Returns:
        Per-share equity value
    """
    enterprise_value = metric * multiple
    equity_value = enterprise_value + cash - debt
    
    if diluted_shares <= 0:
        logger.warning("Diluted shares must be positive")
        return 0.0
    
    per_share_value = equity_value / diluted_shares
    return per_share_value


def expected_return(
    bear_value: float,
    base_value: float,
    bull_value: float,
    current_price: float,
    p_bear: float,
    p_base: float,
    p_bull: float,
    dividend_yield: float = 0.0,
) -> float:
    """
    Calculate expected 12-month return.
    
    Args:
        bear_value: Bear case valuation
        base_value: Base case valuation
        bull_value: Bull case valuation
        current_price: Current stock price
        p_bear: Probability of bear case
        p_base: Probability of base case
        p_bull: Probability of bull case
        dividend_yield: Annual dividend yield
    
    Returns:
        Expected return
    """
    if current_price <= 0:
        logger.warning("Current price must be positive")
        return 0.0
    
    bear_return = (bear_value / current_price) - 1
    base_return = (base_value / current_price) - 1
    bull_return = (bull_value / current_price) - 1
    
    expected = (
        p_bear * bear_return +
        p_base * base_return +
        p_bull * bull_return +
        dividend_yield
    )
    
    return expected


def downside(bear_value: float, current_price: float) -> float:
    """
    Calculate downside risk.
    
    Args:
        bear_value: Bear case valuation
        current_price: Current stock price
    
    Returns:
        Downside (0 to 1)
    """
    if current_price <= 0:
        return 0.0
    
    ratio = bear_value / current_price
    if ratio < 1:
        return 1 - ratio
    return 0.0


def upside(base_value: float, current_price: float) -> float:
    """
    Calculate upside potential.
    
    Args:
        base_value: Base case valuation
        current_price: Current stock price
    
    Returns:
        Upside (0 to 1)
    """
    if current_price <= 0:
        return 0.0
    
    ratio = base_value / current_price
    if ratio > 1:
        return ratio - 1
    return 0.0


def upside_downside_ratio(upside: float, downside: float, epsilon: float = 0.01) -> float:
    """
    Calculate upside/downside ratio.
    
    Args:
        upside: Upside potential
        downside: Downside risk
        epsilon: Small value to avoid division by zero
    
    Returns:
        Upside/downside ratio
    """
    denom = max(downside, epsilon)
    return upside / denom


def margin_of_safety(base_value: float, current_price: float) -> float:
    """
    Calculate margin of safety.
    
    Args:
        base_value: Base case valuation
        current_price: Current stock price
    
    Returns:
        Margin of safety (0 to 1)
    """
    if base_value <= 0:
        return 0.0
    
    return (base_value - current_price) / base_value
