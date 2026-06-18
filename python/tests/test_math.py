"""
Tests for mathematical framework
"""

import pytest
from shrek_ai.math import (
    scenario_valuation,
    dcf_valuation,
    multiple_valuation,
    expected_return,
    downside,
    upside,
    upside_downside_ratio,
    margin_of_safety,
    piotroski_f_score,
    business_quality_score,
    logit,
    logit_to_probability,
    bayesian_thesis_update,
    kelly_fraction,
    fractional_kelly,
    adjust_kelly_for_risk,
    position_size,
    drawdown,
    max_drawdown,
    investability_gate,
    entry_decision,
)


def test_scenario_valuation():
    """Test scenario valuation calculation"""
    bear_scenarios = {'dcf': 80, 'pe': 75, 'ev_ebitda': 85}
    base_scenarios = {'dcf': 100, 'pe': 105, 'ev_ebitda': 95}
    bull_scenarios = {'dcf': 150, 'pe': 140, 'ev_ebitda': 160}
    
    bear, base, bull = scenario_valuation(bear_scenarios, base_scenarios, bull_scenarios)
    
    assert bear < base < bull
    assert 70 < bear < 90
    assert 90 < base < 110
    assert 130 < bull < 170


def test_dcf_valuation():
    """Test DCF valuation"""
    fcf_current = 1000000
    growth_rates = (0.10, 0.08, 0.06, 0.05, 0.04)
    terminal_growth = 0.03
    wacc = 0.10
    cash = 50000000
    debt = 30000000
    diluted_shares = 10000000
    
    value = dcf_valuation(
        fcf_current, growth_rates, terminal_growth, wacc,
        cash, debt, 0, 0, diluted_shares
    )
    
    assert value > 0
    assert value < 100  # Sanity check


def test_multiple_valuation():
    """Test multiple valuation"""
    metric = 1000000000
    multiple = 20
    cash = 50000000
    debt = 30000000
    diluted_shares = 10000000
    
    value = multiple_valuation(metric, multiple, cash, debt, diluted_shares)
    
    assert value > 0
    assert value < 2500  # Sanity check: (1B*20 + 50M - 30M)/10M ≈ $2002


def test_expected_return():
    """Test expected return calculation"""
    bear_value = 80
    base_value = 100
    bull_value = 150
    current_price = 100
    p_bear = 0.30
    p_base = 0.50
    p_bull = 0.20
    
    exp_return = expected_return(
        bear_value, base_value, bull_value, current_price,
        p_bear, p_base, p_bull
    )
    
    assert -0.5 < exp_return < 0.5


def test_downside():
    """Test downside calculation"""
    assert downside(80, 100) == pytest.approx(0.20)
    assert downside(120, 100) == 0.0


def test_upside():
    """Test upside calculation"""
    assert upside(120, 100) == pytest.approx(0.20)
    assert upside(80, 100) == 0.0


def test_upside_downside_ratio():
    """Test upside/downside ratio"""
    assert upside_downside_ratio(0.30, 0.10) == pytest.approx(3.0)
    assert upside_downside_ratio(0.10, 0.30) == pytest.approx(0.333, rel=0.01)


def test_margin_of_safety():
    """Test margin of safety"""
    assert margin_of_safety(120, 100) == pytest.approx(0.167, rel=0.01)
    assert margin_of_safety(100, 100) == 0.0


def test_piotroski_f_score():
    """Test Piotroski F-Score"""
    score = piotroski_f_score(
        roa=0.10,
        cfo=1000000,
        roa_prior=0.08,
        net_income=1000000,
        long_term_debt_ratio_current=0.30,
        long_term_debt_ratio_prior=0.35,
        current_ratio_current=2.0,
        current_ratio_prior=1.8,
        shares_outstanding_current=1000000,
        shares_outstanding_prior=1000000,
        gross_margin_current=0.40,
        gross_margin_prior=0.38,
        asset_turnover_current=1.2,
        asset_turnover_prior=1.1,
    )
    
    assert 0 <= score <= 9


def test_business_quality_score():
    """Test business quality score"""
    score = business_quality_score(
        revenue_growth=0.15,
        gross_margin=0.40,
        operating_margin=0.25,
        fcf_margin=0.20,
        roic=0.15,
        balance_sheet=0.70,
        piotroski=0.70,
        dilution=0.90,
    )
    
    assert 0 <= score <= 1


def test_logit():
    """Test logit conversion"""
    assert logit(0.5) == 0.0
    assert logit(0.75) > 0
    assert logit(0.25) < 0


def test_logit_to_probability():
    """Test logit to probability conversion"""
    assert logit_to_probability(0.0) == 0.5
    assert logit_to_probability(1.0) > 0.5
    assert logit_to_probability(-1.0) < 0.5


def test_bayesian_thesis_update():
    """Test Bayesian thesis update"""
    current_prob = 0.70
    updated = bayesian_thesis_update(
        current_prob,
        evidence_score=0.5,
        evidence_reliability=0.9,
        event_weight=0.35,
    )
    
    assert updated > current_prob


def test_kelly_fraction():
    """Test Kelly fraction"""
    kelly = kelly_fraction(expected_return=0.20, volatility=0.25)
    assert kelly > 0


def test_fractional_kelly():
    """Test fractional Kelly"""
    kelly = kelly_fraction(expected_return=0.20, volatility=0.25)
    fractional = fractional_kelly(kelly, fraction=0.25)
    assert fractional == kelly * 0.25


def test_adjust_kelly_for_risk():
    """Test Kelly adjustment for risk"""
    kelly = kelly_fraction(expected_return=0.20, volatility=0.25)
    adjusted = adjust_kelly_for_risk(
        kelly,
        thesis_probability=0.70,
        risk_penalty=0.30,
        upside_downside=3.0,
    )
    assert adjusted <= kelly


def test_position_size():
    """Test position size with hard caps"""
    adjusted_kelly = 0.05
    equity = 100000
    max_single_position_pct = 0.10
    
    size = position_size(adjusted_kelly, equity, max_single_position_pct)
    
    assert size <= equity * max_single_position_pct


def test_drawdown():
    """Test drawdown calculation"""
    assert drawdown(90, 100) == pytest.approx(0.10)
    assert drawdown(100, 100) == 0.0


def test_max_drawdown():
    """Test maximum drawdown"""
    prices = [100, 95, 90, 95, 100, 105, 100, 95, 90, 85]
    max_dd = max_drawdown(prices)
    assert max_dd > 0.10


def test_investability_gate():
    """Test investability gate"""
    result = investability_gate(
        expected_return=0.25,
        upside_downside=3.0,
        quality=0.70,
        risk_penalty=0.30,
        thesis_probability=0.75,
        timing=0.50,
    )
    assert result is True
    
    result = investability_gate(
        expected_return=0.10,
        upside_downside=1.0,
        quality=0.50,
        risk_penalty=0.60,
        thesis_probability=0.50,
        timing=0.30,
    )
    assert result is False


def test_entry_decision():
    """Test entry decision"""
    decision, reason = entry_decision(
        position_exists=False,
        shrek_score=0.80,
        expected_return=0.25,
        upside_downside=3.0,
        quality=0.70,
        risk_penalty=0.30,
        thesis_probability=0.75,
        timing=0.50,
    )
    assert decision == "BUY_STARTER"
    
    decision, reason = entry_decision(
        position_exists=True,
        shrek_score=0.80,
        expected_return=0.25,
        upside_downside=3.0,
        quality=0.70,
        risk_penalty=0.30,
        thesis_probability=0.75,
        timing=0.50,
    )
    assert decision == "HOLD"
