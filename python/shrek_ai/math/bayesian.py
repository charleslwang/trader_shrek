"""
Bayesian thesis update and probability calculations
"""

import math
from typing import Dict, Optional
from loguru import logger


def logit(probability: float) -> float:
    """
    Convert probability to log-odds (logit).
    
    Args:
        probability: Probability (0 to 1)
    
    Returns:
        Log-odds
    """
    if probability <= 0 or probability >= 1:
        logger.warning(f"Probability {probability} must be in (0, 1)")
        return 0.0
    
    return math.log(probability / (1 - probability))


def logit_to_probability(logit: float) -> float:
    """
    Convert log-odds to probability.
    
    Args:
        logit: Log-odds
    
    Returns:
        Probability (0 to 1)
    """
    return 1 / (1 + math.exp(-logit))


def bayesian_thesis_update(
    current_probability: float,
    evidence_score: float,
    evidence_reliability: float,
    event_weight: float,
) -> float:
    """
    Update thesis probability using Bayesian log-odds update.
    
    Args:
        current_probability: Current thesis probability (0 to 1)
        evidence_score: Evidence score (-1 to 1)
        evidence_reliability: Evidence reliability (0 to 1)
        event_weight: Event weight
    
    Returns:
        Updated probability (0 to 1)
    """
    # Convert to logit
    current_logit = logit(current_probability)
    
    # Calculate logit update
    logit_update = event_weight * evidence_score * evidence_reliability
    
    # Update logit
    new_logit = current_logit + logit_update
    
    # Convert back to probability
    new_probability = logit_to_probability(new_logit)
    
    # Clamp to [0.05, 0.95]
    new_probability = max(0.05, min(0.95, new_probability))
    
    return new_probability


def update_scenario_probabilities(
    thesis_probability: float,
    prior_bear: float = 0.30,
    prior_base: float = 0.50,
    prior_bull: float = 0.20,
) -> tuple[float, float, float]:
    """
    Update scenario probabilities based on thesis probability.
    
    Args:
        thesis_probability: Current thesis probability (0 to 1)
        prior_bear: Prior bear probability
        prior_base: Prior base probability
        prior_bull: Prior bull probability
    
    Returns:
        Tuple of (p_bear, p_base, p_bull)
    """
    # Update bull probability based on thesis
    p_bull = max(0.10, min(0.45, 0.20 + 0.50 * (thesis_probability - 0.70)))
    
    # Update bear probability based on thesis
    p_bear = max(0.10, min(0.60, 0.30 + 0.60 * (0.60 - thesis_probability)))
    
    # Base probability is remainder
    p_base = 1.0 - p_bull - p_bear
    
    # Renormalize if needed
    total = p_bear + p_base + p_bull
    if total != 1.0:
        p_bear /= total
        p_base /= total
        p_bull /= total
    
    return p_bear, p_base, p_bull


# Default evidence event weights
EVIDENCE_WEIGHTS = {
    'earnings_beat_margin_expansion': 0.35,
    'earnings_miss_margin_compression': -0.35,
    'guidance_raise': 0.40,
    'guidance_cut': -0.45,
    'fcf_improvement': 0.25,
    'fcf_deterioration': -0.25,
    'debt_reduction': 0.15,
    'debt_stress': -0.30,
    'dilution': -0.25,
    'insider_buying': 0.15,
    'insider_selling': -0.10,
    'accounting_red_flag': -0.60,
    'regulatory_investigation': -0.50,
    'product_traction': 0.25,
    'competitive_threat': -0.30,
}


def apply_evidence_event(
    current_probability: float,
    event_type: str,
    evidence_score: float,
    evidence_reliability: float = 0.9,
    custom_weights: Optional[Dict[str, float]] = None,
) -> float:
    """
    Apply a specific evidence event to thesis probability.
    
    Args:
        current_probability: Current thesis probability
        event_type: Type of evidence event
        evidence_score: Evidence score (-1 to 1)
        evidence_reliability: Evidence reliability (0 to 1)
        custom_weights: Optional custom event weights
    
    Returns:
        Updated probability
    """
    weights = custom_weights if custom_weights else EVIDENCE_WEIGHTS
    
    event_weight = weights.get(event_type, 0.0)
    
    return bayesian_thesis_update(
        current_probability,
        evidence_score,
        evidence_reliability,
        event_weight,
    )
