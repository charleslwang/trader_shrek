"""
Research a single company
"""

import sys
import uuid
from pathlib import Path
from datetime import datetime
from loguru import logger

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from shrek_ai.config import load_config, load_env
from shrek_ai.alpaca_data import AlpacaDataSource
from shrek_ai.alpaca_account import AlpacaAccount
from shrek_ai.sec_edgar import SECEdgar
from shrek_ai.filings import FilingManager
from shrek_ai.fundamentals import FundamentalsProcessor
from shrek_ai.agents import (
    FilingAnalyst,
    EarningsAnalyst,
    ValuationAnalyst,
    RiskAnalyst,
    TimingAnalyst,
    PortfolioManager,
)
from shrek_ai.memory import MemorySystem
from shrek_ai.storage import StorageManager
from shrek_ai.math import (
    scenario_valuation,
    expected_return,
    downside,
    upside,
    upside_downside_ratio,
    margin_of_safety,
    business_quality_score,
    piotroski_score,
    revision_score,
    timing_score,
    risk_penalty,
    shrek_score,
    logit_to_probability,
    update_scenario_probabilities,
    bayesian_thesis_update,
    apply_evidence_event,
    investability_gate,
    entry_decision,
)


def research_company(symbol: str):
    """Research a single company"""
    load_env()
    config = load_config()
    
    logger.info(f"Researching {symbol}")
    
    # Initialize components
    alpaca_data = AlpacaDataSource()
    alpaca_account = AlpacaAccount()
    edgar = SECEdgar()
    filing_manager = FilingManager(Path('data/filings'))
    fundamentals_processor = FundamentalsProcessor()
    memory_system = MemorySystem(Path('data/memory'), config=config.memory)
    storage_manager = StorageManager(Path('data/storage'))
    
    # Initialize agents
    filing_analyst = FilingAnalyst()
    earnings_analyst = EarningsAnalyst()
    valuation_analyst = ValuationAnalyst()
    risk_analyst = RiskAnalyst()
    timing_analyst = TimingAnalyst()
    portfolio_manager = PortfolioManager()
    
    # Get current price
    quote = alpaca_data.get_latest_quote(symbol)
    current_price = (quote['bid'] + quote['ask']) / 2
    
    # Get price history for timing
    bars = alpaca_data.get_bars(symbol, timeframe='day', limit=252)
    
    # Download filings
    filing_manager.download_filings(symbol, ['10-K', '10-Q', '8-K'], count=5)
    
    # Get latest 10-K
    tenk = filing_manager.get_latest_10k(symbol)
    
    # Get latest 10-Qs
    tenqs = filing_manager.get_latest_10q(symbol, count=4)
    
    # Run filing analysis
    if tenk:
        filing_analysis = filing_analyst.analyze_filing(
            symbol=symbol,
            filing_type='10-K',
            fiscal_period='FY',
            filing_content=tenk['content'],
        )
        
        # Extract thesis events
        thesis_events = filing_analyst.extract_thesis_events(filing_analysis)
        
        # Store in memory
        for event in thesis_events:
            memory_system.add_memory(
                symbol=symbol,
                layer='deep',
                content=event.get('description', ''),
                relevance=event.get('relevance', 0.8),
                importance=event.get('importance', 0.8),
                source_reliability=0.9,
                source_id='filing_analysis',
            )
    
    # Run valuation analysis
    valuation_analysis = valuation_analyst.analyze_valuation(
        symbol=symbol,
        financial_data={},  # Would be populated from filings
        peer_data=None,
        historical_data=None,
    )
    
    # Calculate valuation scenarios
    valuation_assumptions = valuation_analysis.get('valuation_assumptions', {})
    
    bear_scenarios = valuation_assumptions.get('bear', {})
    base_scenarios = valuation_assumptions.get('base', {})
    bull_scenarios = valuation_assumptions.get('bull', {})
    
    v_bear, v_base, v_bull = scenario_valuation(
        bear_scenarios,
        base_scenarios,
        bull_scenarios,
    )
    
    # Run risk analysis
    risk_analysis = risk_analyst.analyze_risk(
        symbol=symbol,
        financial_data={},
        filing_analysis=filing_analysis if tenk else None,
        news=[],
    )
    
    risk_score = risk_analyst.calculate_risk_score(risk_analysis)
    
    # Run timing analysis
    timing_analysis = timing_analyst.analyze_timing(
        symbol=symbol,
        price_data={'current_price': current_price, 'history': bars.to_dict('records')},
        technical_indicators=None,
    )
    
    # Calculate mathematical scores
    p_bear, p_base, p_bull = update_scenario_probabilities(0.70)
    
    exp_return = expected_return(v_bear, v_base, v_bull, current_price, p_bear, p_base, p_bull)
    down = downside(v_bear, current_price)
    up = upside(v_base, current_price)
    ud_ratio = upside_downside_ratio(up, down)
    mos = margin_of_safety(v_base, current_price)
    
    quality = business_quality_score(
        revenue_growth=0.10,
        gross_margin=0.30,
        operating_margin=0.20,
        fcf_margin=0.15,
        roic=0.15,
        balance_sheet=0.70,
        piotroski=0.70,
        dilution=0.90,
    )
    
    piotroski = piotroski_score(7)
    
    revision = revision_score(
        earnings_surprise=0.5,
        guidance_revision=0.5,
        revenue_acceleration=0.5,
        margin_revision=0.5,
        llm_event=0.5,
    )
    
    timing = timing_score(
        trend_200d=0.5,
        trend_50d=0.5,
        relative_strength=0.5,
        pullback_quality=0.5,
        volume_confirmation=0.5,
    )
    
    risk_pen = risk_penalty(
        balance_sheet_risk=0.3,
        valuation_risk=0.3,
        dilution_risk=0.2,
        volatility_risk=0.3,
        thesis_fragility=0.2,
        accounting_risk=0.1,
        llm_red_flag_risk=0.1,
    )
    
    shrek = shrek_score(
        expected_return_score=min(1.0, max(0.0, (exp_return - 0.05) / 0.35)),
        quality=quality,
        revision=revision,
        timing=timing,
        risk_penalty=risk_pen,
    )
    
    # Run portfolio manager
    decision = portfolio_manager.make_decision(
        symbol=symbol,
        filing_analysis=filing_analysis if tenk else None,
        earnings_analysis=None,
        valuation_analysis=valuation_analysis,
        risk_analysis=risk_analysis,
        timing_analysis=timing_analysis,
        mathematical_scores={
            'expected_return': exp_return,
            'upside_downside': ud_ratio,
            'quality': quality,
            'risk_penalty': risk_pen,
            'thesis_probability': 0.70,
            'timing': timing,
        },
    )
    
    # Save decision
    decision_id = str(uuid.uuid4())
    storage_manager.save_decision({
        'decision_id': decision_id,
        'date': datetime.now().date().isoformat(),
        'symbol': symbol,
        'current_price': current_price,
        'v_bear': v_bear,
        'v_base': v_base,
        'v_bull': v_bull,
        'p_bear': p_bear,
        'p_base': p_base,
        'p_bull': p_bull,
        'expected_return': exp_return,
        'downside': down,
        'upside_downside': ud_ratio,
        'thesis_probability': 0.70,
        'quality_score': quality,
        'piotroski_score': piotroski,
        'revision_score': revision,
        'timing_score': timing,
        'risk_penalty': risk_pen,
        'shrek_score': shrek,
        'decision': decision.get('decision', 'AVOID'),
        'notional': 0.0,
        'order_sent': False,
        'rust_accept': False,
        'rust_reject_reason': None,
        'source_docs': 'filing_analysis,valuation_analysis,risk_analysis,timing_analysis',
        'memo_path': None,
    })
    
    logger.info(f"Research complete for {symbol}: {decision.get('decision')}")
    
    return decision


def main():
    """Main entry point"""
    if len(sys.argv) < 2:
        logger.error("Usage: python research_company.py <symbol>")
        sys.exit(1)
    
    symbol = sys.argv[1]
    research_company(symbol)


if __name__ == '__main__':
    main()
