"""
Entry and add decision logic
"""

from typing import Optional, Tuple
from loguru import logger


def investability_gate(
    expected_return: float,
    upside_downside: float,
    quality: float,
    risk_penalty: float,
    thesis_probability: float,
    timing: float,
    thresholds: Optional[dict] = None,
) -> bool:
    """
    Check if stock passes investability gate.
    
    Args:
        expected_return: Expected return
        upside_downside: Upside/downside ratio
        quality: Quality score
        risk_penalty: Risk penalty
        thesis_probability: Thesis probability
        timing: Timing score
        thresholds: Optional custom thresholds
    
    Returns:
        Whether stock is investable
    """
    if thresholds is None:
        thresholds = {
            'min_expected_return': 0.20,
            'min_upside_downside': 2.0,
            'min_quality': 0.65,
            'max_risk_penalty': 0.45,
            'min_thesis_probability': 0.70,
            'min_timing': 0.45,
        }
    
    checks = {
        'expected_return': expected_return >= thresholds['min_expected_return'],
        'upside_downside': upside_downside >= thresholds['min_upside_downside'],
        'quality': quality >= thresholds['min_quality'],
        'risk_penalty': risk_penalty <= thresholds['max_risk_penalty'],
        'thesis_probability': thesis_probability >= thresholds['min_thesis_probability'],
        'timing': timing >= thresholds['min_timing'],
    }
    
    all_pass = all(checks.values())
    
    if not all_pass:
        failed = [k for k, v in checks.items() if not v]
        logger.debug(f"Investability gate failed: {failed}")
    
    return all_pass


def entry_decision(
    position_exists: bool,
    shrek_score: float,
    expected_return: float,
    upside_downside: float,
    quality: float,
    risk_penalty: float,
    thesis_probability: float,
    timing: float,
    is_speculative: bool = False,
    secular_conviction: float = 0.0,
    narrative_conviction: float = 0.0,
    thresholds: Optional[dict] = None,
) -> Tuple[str, str]:
    """
    Determine entry decision.
    
    Args:
        position_exists: Whether position already exists
        shrek_score: Shrek score
        expected_return: Expected return
        upside_downside: Upside/downside ratio
        quality: Quality score
        risk_penalty: Risk penalty
        thesis_probability: Thesis probability
        timing: Timing score
        is_speculative: Whether this is a speculative/small-cap
        secular_conviction: Secular/platform thesis conviction (0 to 1)
        narrative_conviction: Narrative/TAM expansion conviction (0 to 1)
        thresholds: Optional custom thresholds
    
    Returns:
        Tuple of (decision, reason)
    """
    if position_exists:
        return "HOLD", "Position already exists"
    
    # Check if CONVICTION_BUY criteria are met
    has_conviction = (
        secular_conviction >= 0.70 and
        narrative_conviction >= 0.70 and
        risk_penalty <= 0.55 and
        quality >= 0.60 and
        thesis_probability >= 0.65
    )
    
    # Use appropriate thresholds
    if is_speculative:
        if thresholds is None:
            thresholds = {
                'min_shrek_score': 0.82,
                'min_expected_return': 0.30,
                'min_upside_downside': 3.0,
                'min_quality': 0.55,
                'max_risk_penalty': 0.55,
                'min_thesis_probability': 0.75,
                'min_timing': 0.50,
            }
    else:
        if thresholds is None:
            thresholds = {
                'min_shrek_score': 0.75,
                'min_expected_return': 0.20,
                'min_upside_downside': 2.0,
                'min_quality': 0.65,
                'max_risk_penalty': 0.45,
                'min_thesis_probability': 0.70,
                'min_timing': 0.45,
            }
    
    # If conviction buy criteria met, use RELAXED thresholds
    if has_conviction:
        relaxed_thresholds = thresholds.copy()
        relaxed_thresholds['min_expected_return'] = 0.12  # Down from 20%
        relaxed_thresholds['min_upside_downside'] = 1.5   # Down from 2.0x
        relaxed_thresholds['min_shrek_score'] = 0.65      # Down from 0.75
        relaxed_thresholds['min_timing'] = 0.35            # Down from 0.45
        
        # Check investability gate with relaxed thresholds
        if not investability_gate(
            expected_return,
            upside_downside,
            quality,
            risk_penalty,
            thesis_probability,
            timing,
            relaxed_thresholds,
        ):
            return "AVOID", "Fails even relaxed investability gate for conviction thesis"
        
        # Check relaxed Shrek score
        if shrek_score < relaxed_thresholds['min_shrek_score']:
            return "WATCH", f"Shrek score {shrek_score:.2f} below relaxed conviction threshold {relaxed_thresholds['min_shrek_score']}"
        
        return "CONVICTION_BUY", f"Secular conviction {secular_conviction:.0%} + narrative conviction {narrative_conviction:.0%} with relaxed thresholds"
    
    # Standard path
    # Check investability gate
    if not investability_gate(
        expected_return,
        upside_downside,
        quality,
        risk_penalty,
        thesis_probability,
        timing,
        thresholds,
    ):
        return "AVOID", "Fails investability gate"
    
    # Check Shrek score
    if shrek_score < thresholds['min_shrek_score']:
        return "WATCH", f"Shrek score {shrek_score:.2f} below threshold {thresholds['min_shrek_score']}"
    
    return "BUY_STARTER", "Passes all entry thresholds"


def add_decision(
    current_position_value: float,
    entry_thesis_probability: float,
    current_thesis_probability: float,
    entry_expected_return: float,
    current_expected_return: float,
    current_shrek_score: float,
    current_risk_penalty: float,
    current_price: float,
    entry_price: float,
    thesis_breaking_events: list,
    guidance_cut: bool,
    accounting_red_flag: bool,
    max_single_position_pct: float,
    equity: float,
    target_position_value: float,
) -> Tuple[str, str]:
    """
    Determine add decision.
    
    Args:
        current_position_value: Current position value
        entry_thesis_probability: Thesis probability at entry
        current_thesis_probability: Current thesis probability
        entry_expected_return: Expected return at entry
        current_expected_return: Current expected return
        current_shrek_score: Current Shrek score
        current_risk_penalty: Current risk penalty
        current_price: Current price
        entry_price: Entry price
        thesis_breaking_events: List of thesis-breaking events
        guidance_cut: Whether guidance was cut
        accounting_red_flag: Whether accounting red flag exists
        max_single_position_pct: Max position as percentage of equity
        equity: Total equity
        target_position_value: Target position value
    
    Returns:
        Tuple of (decision, reason)
    """
    # Reject if thesis has degraded too much
    if current_thesis_probability < entry_thesis_probability - 0.10:
        return "HOLD", f"Thesis degraded from {entry_thesis_probability:.2%} to {current_thesis_probability:.2%}"
    
    # Reject if risk increased too much
    if current_risk_penalty > 0.65:
        return "HOLD", f"Risk penalty elevated: {current_risk_penalty:.2f}"
    
    # Reject if thesis-breaking events exist
    if thesis_breaking_events:
        return "TRIM", f"Thesis-breaking events: {', '.join(thesis_breaking_events)}"
    
    # Reject if guidance was cut
    if guidance_cut:
        return "HOLD", "Guidance cut"
    
    # Reject if accounting red flag exists
    if accounting_red_flag:
        return "TRIM", "Accounting red flag"
    
    # Check if position already at max
    current_position_pct = current_position_value / equity
    if current_position_pct >= max_single_position_pct:
        return "HOLD", "Position already at maximum size"
    
    # Check if expected return improved
    if current_price < entry_price:
        if current_expected_return > entry_expected_return:
            # Good add on pullback
            if current_shrek_score >= 0.78:
                return "ADD", "Add on pullback with improved expected return"
            else:
                return "HOLD", f"Shrek score {current_shrek_score:.2f} below add threshold"
        else:
            return "HOLD", "Expected return not improved on pullback"
    else:
        # Price is above entry, check if still attractive
        if current_shrek_score >= 0.78 and current_expected_return >= entry_expected_return:
            return "ADD", "Add with maintained thesis and expected return"
        else:
            return "HOLD", "Price above entry without improved metrics"


def add_on_pullback_decision(
    current_price: float,
    entry_price: float,
    current_expected_return: float,
    entry_expected_return: float,
    current_thesis_probability: float,
    entry_thesis_probability: float,
    current_risk_penalty: float,
    entry_risk_penalty: float,
    thesis_breaking_events: list,
    guidance_cut: bool,
) -> Tuple[str, str]:
    """
    Determine add-on-pullback decision.
    
    Args:
        current_price: Current price
        entry_price: Entry price
        current_expected_return: Current expected return
        entry_expected_return: Expected return at entry
        current_thesis_probability: Current thesis probability
        entry_thesis_probability: Thesis probability at entry
        current_risk_penalty: Current risk penalty
        entry_risk_penalty: Risk penalty at entry
        thesis_breaking_events: List of thesis-breaking events
        guidance_cut: Whether guidance was cut
    
    Returns:
        Tuple of (decision, reason)
    """
    # Only consider if price is below entry
    if current_price >= entry_price:
        return "HOLD", "Price not below entry"
    
    # Check if expected return improved
    if current_expected_return <= entry_expected_return:
        return "HOLD", "Expected return not improved"
    
    # Check if thesis still intact
    if current_thesis_probability < entry_thesis_probability - 0.10:
        return "HOLD", "Thesis degraded too much"
    
    # Check if risk increased too much
    if current_risk_penalty > entry_risk_penalty + 0.15:
        return "HOLD", "Risk increased too much"
    
    # Reject if thesis-breaking events exist
    if thesis_breaking_events:
        return "HOLD", "Thesis-breaking events exist"
    
    # Reject if guidance was cut
    if guidance_cut:
        return "HOLD", "Guidance cut"
    
    return "ADD_ON_PULLBACK", "Add on pullback with improved expected return and intact thesis"
