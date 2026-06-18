"""
Mathematical framework for Shrek
"""

from .valuation import (
    scenario_valuation,
    dcf_valuation,
    multiple_valuation,
    expected_return,
    downside,
    upside,
    upside_downside_ratio,
    margin_of_safety,
)
from .quality import (
    piotroski_f_score,
    business_quality_score,
    revenue_growth_score,
    gross_margin_score,
    operating_margin_score,
    fcf_margin_score,
    roic_score,
    balance_sheet_score,
    dilution_score,
)
from .factors import (
    revision_score,
    timing_score,
    risk_penalty,
    shrek_score,
)
from .bayesian import (
    logit,
    logit_to_probability,
    bayesian_thesis_update,
    update_scenario_probabilities,
)
from .sizing import (
    kelly_fraction,
    fractional_kelly,
    adjust_kelly_for_risk,
    position_size,
    starter_position_size,
    add_position_size,
)
from .exits import (
    trim_decision,
    sell_decision,
    forward_expected_return,
)
from .drawdown import (
    drawdown,
    max_drawdown,
    drawdown_quantile,
    drawdown_stop_price,
)
from .decisions import (
    entry_decision,
    add_decision,
    investability_gate,
)

__all__ = [
    # Valuation
    'scenario_valuation',
    'dcf_valuation',
    'multiple_valuation',
    'expected_return',
    'downside',
    'upside',
    'upside_downside_ratio',
    'margin_of_safety',
    # Quality
    'piotroski_f_score',
    'business_quality_score',
    'revenue_growth_score',
    'gross_margin_score',
    'operating_margin_score',
    'fcf_margin_score',
    'roic_score',
    'balance_sheet_score',
    'dilution_score',
    # Factors
    'revision_score',
    'timing_score',
    'risk_penalty',
    'shrek_score',
    # Bayesian
    'logit',
    'logit_to_probability',
    'bayesian_thesis_update',
    'update_scenario_probabilities',
    # Sizing
    'kelly_fraction',
    'fractional_kelly',
    'adjust_kelly_for_risk',
    'position_size',
    'starter_position_size',
    'add_position_size',
    # Exits
    'trim_decision',
    'sell_decision',
    'forward_expected_return',
    # Drawdown
    'drawdown',
    'max_drawdown',
    'drawdown_quantile',
    'drawdown_stop_price',
    # Decisions
    'entry_decision',
    'add_decision',
    'investability_gate',
]
