"""
Factor scoring models
"""

from typing import Dict, Optional
from loguru import logger


def revision_score(
    earnings_surprise: float,
    guidance_revision: float,
    revenue_acceleration: float,
    margin_revision: float,
    llm_event: float,
    weights: Optional[Dict[str, float]] = None,
) -> float:
    """
    Calculate revision score.
    
    Args:
        earnings_surprise: Earnings surprise score (0 to 1)
        guidance_revision: Guidance revision score (0 to 1)
        revenue_acceleration: Revenue acceleration score (0 to 1)
        margin_revision: Margin revision score (0 to 1)
        llm_event: LLM event score (0 to 1)
        weights: Optional custom weights
    
    Returns:
        Revision score (0 to 1)
    """
    if weights is None:
        weights = {
            'earnings_surprise': 0.25,
            'guidance_revision': 0.25,
            'revenue_acceleration': 0.20,
            'margin_revision': 0.15,
            'llm_event': 0.15,
        }
    
    return (
        weights['earnings_surprise'] * earnings_surprise +
        weights['guidance_revision'] * guidance_revision +
        weights['revenue_acceleration'] * revenue_acceleration +
        weights['margin_revision'] * margin_revision +
        weights['llm_event'] * llm_event
    )


def timing_score(
    trend_200d: float,
    trend_50d: float,
    relative_strength: float,
    pullback_quality: float,
    volume_confirmation: float,
    weights: Optional[Dict[str, float]] = None,
) -> float:
    """
    Calculate technical timing score.
    
    Args:
        trend_200d: 200-day trend score (0 to 1)
        trend_50d: 50-day trend score (0 to 1)
        relative_strength: Relative strength score (0 to 1)
        pullback_quality: Pullback quality score (0 to 1)
        volume_confirmation: Volume confirmation score (0 to 1)
        weights: Optional custom weights
    
    Returns:
        Timing score (0 to 1)
    """
    if weights is None:
        weights = {
            'trend_200d': 0.25,
            'trend_50d': 0.20,
            'relative_strength': 0.20,
            'pullback_quality': 0.20,
            'volume_confirmation': 0.15,
        }
    
    return (
        weights['trend_200d'] * trend_200d +
        weights['trend_50d'] * trend_50d +
        weights['relative_strength'] * relative_strength +
        weights['pullback_quality'] * pullback_quality +
        weights['volume_confirmation'] * volume_confirmation
    )


def risk_penalty(
    balance_sheet_risk: float,
    valuation_risk: float,
    dilution_risk: float,
    volatility_risk: float,
    thesis_fragility: float,
    accounting_risk: float,
    llm_red_flag_risk: float,
    weights: Optional[Dict[str, float]] = None,
) -> float:
    """
    Calculate risk penalty (higher is worse).
    
    Args:
        balance_sheet_risk: Balance sheet risk (0 to 1)
        valuation_risk: Valuation risk (0 to 1)
        dilution_risk: Dilution risk (0 to 1)
        volatility_risk: Volatility risk (0 to 1)
        thesis_fragility: Thesis fragility (0 to 1)
        accounting_risk: Accounting risk (0 to 1)
        llm_red_flag_risk: LLM red flag risk (0 to 1)
        weights: Optional custom weights
    
    Returns:
        Risk penalty (0 to 1)
    """
    if weights is None:
        weights = {
            'balance_sheet': 0.20,
            'valuation': 0.15,
            'dilution': 0.15,
            'volatility': 0.15,
            'thesis_fragility': 0.15,
            'accounting': 0.10,
            'llm_red_flag': 0.10,
        }
    
    return (
        weights['balance_sheet'] * balance_sheet_risk +
        weights['valuation'] * valuation_risk +
        weights['dilution'] * dilution_risk +
        weights['volatility'] * volatility_risk +
        weights['thesis_fragility'] * thesis_fragility +
        weights['accounting'] * accounting_risk +
        weights['llm_red_flag'] * llm_red_flag_risk
    )


def shrek_score(
    expected_return_score: float,
    quality: float,
    revision: float,
    timing: float,
    risk_penalty: float,
    secular_conviction: float = 0.0,
    weights: Optional[Dict[str, float]] = None,
) -> float:
    """
    Calculate overall Shrek score.
    
    Args:
        expected_return_score: Expected return score (0 to 1)
        quality: Quality score (0 to 1)
        revision: Revision score (0 to 1)
        timing: Timing score (0 to 1)
        risk_penalty: Risk penalty (0 to 1)
        secular_conviction: Secular/platform thesis conviction (0 to 1)
        weights: Optional custom weights
    
    Returns:
        Shrek score (0 to 1)
    """
    if weights is None:
        weights = {
            'expected_return': 0.25,
            'quality': 0.20,
            'revision': 0.15,
            'timing': 0.10,
            'risk_penalty': 0.10,
            'secular_conviction': 0.20,
        }
    
    score = (
        weights['expected_return'] * expected_return_score +
        weights['quality'] * quality +
        weights['revision'] * revision +
        weights['timing'] * timing +
        weights['secular_conviction'] * secular_conviction -
        weights['risk_penalty'] * risk_penalty
    )
    
    # Clamp to [0, 1]
    return max(0.0, min(1.0, score))


def expected_return_score(expected_return: float) -> float:
    """
    Normalize expected return to 0-1 range.
    
    Maps 5% expected return to 0 and 40% expected return to 1.
    
    Args:
        expected_return: Expected return (0 to 1)
    
    Returns:
        Normalized score (0 to 1)
    """
    return max(0.0, min(1.0, (expected_return - 0.05) / 0.35))
