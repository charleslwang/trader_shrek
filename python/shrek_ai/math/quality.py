"""
Quality scoring models
"""

from typing import Dict, Optional
from loguru import logger


def piotroski_f_score(
    roa: float,
    cfo: float,
    roa_prior: float,
    net_income: float,
    long_term_debt_ratio_current: float,
    long_term_debt_ratio_prior: float,
    current_ratio_current: float,
    current_ratio_prior: float,
    shares_outstanding_current: float,
    shares_outstanding_prior: float,
    gross_margin_current: float,
    gross_margin_prior: float,
    asset_turnover_current: float,
    asset_turnover_prior: float,
) -> int:
    """
    Calculate Piotroski F-Score.
    
    Args:
        roa: Current return on assets
        cfo: Current cash flow from operations
        roa_prior: Prior period return on assets
        net_income: Current net income
        long_term_debt_ratio_current: Current long-term debt ratio
        long_term_debt_ratio_prior: Prior long-term debt ratio
        current_ratio_current: Current current ratio
        current_ratio_prior: Prior current ratio
        shares_outstanding_current: Current shares outstanding
        shares_outstanding_prior: Prior shares outstanding
        gross_margin_current: Current gross margin
        gross_margin_prior: Prior gross margin
        asset_turnover_current: Current asset turnover
        asset_turnover_prior: Prior asset turnover
    
    Returns:
        Piotroski F-Score (0-9)
    """
    f1 = 1 if roa > 0 else 0
    f2 = 1 if cfo > 0 else 0
    f3 = 1 if roa > roa_prior else 0
    f4 = 1 if cfo > net_income else 0
    f5 = 1 if long_term_debt_ratio_current < long_term_debt_ratio_prior else 0
    f6 = 1 if current_ratio_current > current_ratio_prior else 0
    f7 = 1 if shares_outstanding_current <= shares_outstanding_prior else 0
    f8 = 1 if gross_margin_current > gross_margin_prior else 0
    f9 = 1 if asset_turnover_current > asset_turnover_prior else 0
    
    return f1 + f2 + f3 + f4 + f5 + f6 + f7 + f8 + f9


def piotroski_score(f_score: int) -> float:
    """
    Normalize Piotroski F-Score to 0-1 range.
    
    Args:
        f_score: Piotroski F-Score (0-9)
    
    Returns:
        Normalized score (0-1)
    """
    return f_score / 9.0


def revenue_growth_score(revenue_growth: float) -> float:
    """
    Calculate revenue growth score.
    
    Args:
        revenue_growth: Revenue growth rate (0 to 1)
    
    Returns:
        Score (0 to 1)
    """
    if revenue_growth <= 0:
        return 0.0
    elif revenue_growth >= 0.30:
        return 1.0
    elif revenue_growth <= 0.10:
        return 0.5 * (revenue_growth / 0.10)
    else:
        return 0.5 + 0.5 * ((revenue_growth - 0.10) / 0.20)


def gross_margin_score(gross_margin: float, sector_percentile: Optional[float] = None) -> float:
    """
    Calculate gross margin score.
    
    Args:
        gross_margin: Gross margin (0 to 1)
        sector_percentile: Sector percentile (0 to 1)
    
    Returns:
        Score (0 to 1)
    """
    if sector_percentile is not None:
        return sector_percentile
    
    # Fallback: use absolute margin
    if gross_margin >= 0.50:
        return 1.0
    elif gross_margin >= 0.30:
        return 0.75
    elif gross_margin >= 0.20:
        return 0.50
    elif gross_margin >= 0.10:
        return 0.25
    else:
        return 0.0


def operating_margin_score(operating_margin: float, sector_percentile: Optional[float] = None) -> float:
    """
    Calculate operating margin score.
    
    Args:
        operating_margin: Operating margin (0 to 1)
        sector_percentile: Sector percentile (0 to 1)
    
    Returns:
        Score (0 to 1)
    """
    if sector_percentile is not None:
        return sector_percentile
    
    # Fallback: use absolute margin
    if operating_margin >= 0.30:
        return 1.0
    elif operating_margin >= 0.20:
        return 0.75
    elif operating_margin >= 0.10:
        return 0.50
    elif operating_margin >= 0.05:
        return 0.25
    else:
        return 0.0


def fcf_margin_score(fcf_margin: float, sector_percentile: Optional[float] = None) -> float:
    """
    Calculate FCF margin score.
    
    Args:
        fcf_margin: Free cash flow margin (0 to 1)
        sector_percentile: Sector percentile (0 to 1)
    
    Returns:
        Score (0 to 1)
    """
    if sector_percentile is not None:
        return sector_percentile
    
    # Fallback: use absolute margin
    if fcf_margin >= 0.20:
        return 1.0
    elif fcf_margin >= 0.15:
        return 0.75
    elif fcf_margin >= 0.10:
        return 0.50
    elif fcf_margin >= 0.05:
        return 0.25
    else:
        return 0.0


def roic_score(roic: float) -> float:
    """
    Calculate ROIC score.
    
    Args:
        roic: Return on invested capital (0 to 1)
    
    Returns:
        Score (0 to 1)
    """
    if roic <= 0:
        return 0.0
    elif roic >= 0.25:
        return 1.0
    elif roic <= 0.10:
        return 0.5 * (roic / 0.10)
    else:
        return 0.5 + 0.5 * ((roic - 0.10) / 0.15)


def balance_sheet_score(
    cash_debt_score: float,
    current_ratio_score: float,
    interest_coverage_score: float,
) -> float:
    """
    Calculate balance sheet score.
    
    Args:
        cash_debt_score: Cash/debt score (0 to 1)
        current_ratio_score: Current ratio score (0 to 1)
        interest_coverage_score: Interest coverage score (0 to 1)
    
    Returns:
        Score (0 to 1)
    """
    return (
        0.40 * cash_debt_score +
        0.30 * current_ratio_score +
        0.30 * interest_coverage_score
    )


def dilution_score(share_dilution_rate: float) -> float:
    """
    Calculate dilution score.
    
    Args:
        share_dilution_rate: Annual share dilution rate (0 to 1)
    
    Returns:
        Score (0 to 1)
    """
    if share_dilution_rate >= 0.10:
        return 0.0
    else:
        return 1.0 - min(share_dilution_rate / 0.10, 1.0)


def business_quality_score(
    revenue_growth: float,
    gross_margin: float,
    operating_margin: float,
    fcf_margin: float,
    roic: float,
    balance_sheet: float,
    piotroski: float,
    dilution: float,
    weights: Optional[Dict[str, float]] = None,
) -> float:
    """
    Calculate overall business quality score.
    
    Args:
        revenue_growth: Revenue growth score (0 to 1)
        gross_margin: Gross margin score (0 to 1)
        operating_margin: Operating margin score (0 to 1)
        fcf_margin: FCF margin score (0 to 1)
        roic: ROIC score (0 to 1)
        balance_sheet: Balance sheet score (0 to 1)
        piotroski: Piotroski score (0 to 1)
        dilution: Dilution score (0 to 1)
        weights: Optional custom weights
    
    Returns:
        Overall quality score (0 to 1)
    """
    if weights is None:
        weights = {
            'revenue_growth': 0.15,
            'gross_margin': 0.15,
            'operating_margin': 0.15,
            'fcf_margin': 0.15,
            'roic': 0.15,
            'balance_sheet': 0.10,
            'piotroski': 0.10,
            'dilution': 0.05,
        }
    
    return (
        weights['revenue_growth'] * revenue_growth +
        weights['gross_margin'] * gross_margin +
        weights['operating_margin'] * operating_margin +
        weights['fcf_margin'] * fcf_margin +
        weights['roic'] * roic +
        weights['balance_sheet'] * balance_sheet +
        weights['piotroski'] * piotroski +
        weights['dilution'] * dilution
    )
