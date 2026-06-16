"""
Exit decision calculations
"""

from typing import Optional, Tuple
from loguru import logger


def forward_expected_return(
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
    Calculate forward expected return after price change.
    
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
        Forward expected return
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


def trim_decision(
    forward_return: float,
    current_price: float,
    base_value: float,
    upside_downside: float,
    current_position_pct: float,
    max_single_position_pct: float,
    position_gain: float,
    risk_penalty: float,
    trim_thresholds: Optional[dict] = None,
) -> Tuple[bool, str]:
    """
    Determine if position should be trimmed.
    
    Args:
        forward_return: Forward expected return
        current_price: Current stock price
        base_value: Base case valuation
        upside_downside: Upside/downside ratio
        current_position_pct: Current position as percentage of portfolio
        max_single_position_pct: Max position as percentage of portfolio
        position_gain: Position gain since entry (0 to 1)
        risk_penalty: Risk penalty
        trim_thresholds: Optional custom thresholds
    
    Returns:
        Tuple of (should_trim, reason)
    """
    if trim_thresholds is None:
        trim_thresholds = {
            'trim_forward_return_below': 0.08,
            'trim_upside_downside_below': 1.20,
        }
    
    reasons = []
    
    # Trim if forward expected return is low
    if forward_return < trim_thresholds['trim_forward_return_below']:
        reasons.append(f"Forward return {forward_return:.2%} below threshold")
    
    # Trim if upside/downside ratio is low
    if upside_downside < trim_thresholds['trim_upside_downside_below']:
        reasons.append(f"Upside/downside {upside_downside:.2f} below threshold")
    
    # Trim if position reached base valuation
    if current_price >= base_value:
        reasons.append("Price reached base valuation")
    
    # Trim if position is too large
    if current_position_pct > max_single_position_pct:
        reasons.append(f"Position {current_position_pct:.2%} exceeds max {max_single_position_pct:.2%}")
    
    # Trim if large gain and risk increased
    if position_gain > 0.50 and risk_penalty > 0.50:
        reasons.append(f"Large gain {position_gain:.2%} with elevated risk")
    
    should_trim = len(reasons) > 0
    reason = "; ".join(reasons) if reasons else "No trim reason"
    
    return should_trim, reason


def sell_decision(
    forward_return: float,
    thesis_probability: float,
    shrek_score: float,
    risk_penalty: float,
    thesis_break_events: list,
    better_opportunity: bool = False,
    sell_thresholds: Optional[dict] = None,
) -> Tuple[bool, str]:
    """
    Determine if position should be sold.
    
    Args:
        forward_return: Forward expected return
        thesis_probability: Thesis probability
        shrek_score: Shrek score
        risk_penalty: Risk penalty
        thesis_break_events: List of thesis-breaking events
        better_opportunity: Whether a better opportunity exists
        sell_thresholds: Optional custom thresholds
    
    Returns:
        Tuple of (should_sell, reason)
    """
    if sell_thresholds is None:
        sell_thresholds = {
            'sell_forward_return_below': 0.00,
            'sell_thesis_probability_below': 0.50,
            'sell_shrek_score_below': 0.55,
            'sell_risk_penalty_above': 0.70,
        }
    
    reasons = []
    
    # Sell if forward expected return is negative
    if forward_return < sell_thresholds['sell_forward_return_below']:
        reasons.append(f"Forward return {forward_return:.2%} is negative")
    
    # Sell if thesis probability is too low
    if thesis_probability < sell_thresholds['sell_thesis_probability_below']:
        reasons.append(f"Thesis probability {thesis_probability:.2%} below threshold")
    
    # Sell if Shrek score is too low
    if shrek_score < sell_thresholds['sell_shrek_score_below']:
        reasons.append(f"Shrek score {shrek_score:.2f} below threshold")
    
    # Sell if risk penalty is too high
    if risk_penalty > sell_thresholds['sell_risk_penalty_above']:
        reasons.append(f"Risk penalty {risk_penalty:.2f} above threshold")
    
    # Sell if thesis-breaking events exist
    if thesis_break_events:
        reasons.append(f"Thesis-breaking events: {', '.join(thesis_break_events)}")
    
    # Sell if better opportunity dominates
    if better_opportunity:
        reasons.append("Better opportunity dominates on risk-adjusted return")
    
    should_sell = len(reasons) > 0
    reason = "; ".join(reasons) if reasons else "No sell reason"
    
    return should_sell, reason


def trim_amount(
    current_position_value: float,
    trim_percentage: float = 0.25,
    min_notional: float = 1.0,
) -> float:
    """
    Calculate trim amount.
    
    Args:
        current_position_value: Current position value
        trim_percentage: Percentage to trim (default 25%)
        min_notional: Minimum notional to keep
    
    Returns:
        Trim notional
    """
    trim_value = current_position_value * trim_percentage
    remaining = current_position_value - trim_value
    
    # Don't trim below minimum notional
    if remaining < min_notional:
        trim_value = current_position_value - min_notional
    
    return max(0.0, trim_value)


THESIS_BREAK_EVENTS = [
    'guidance_cut_invalidating_growth',
    'margin_collapse_unexplained',
    'severe_dilution',
    'debt_covenant_liquidity_crisis',
    'regulatory_investigation',
    'fraud_accounting_restatement',
    'management_credibility_break',
    'product_business_thesis_invalidated',
    'competitive_moat_weakened_materially',
]
