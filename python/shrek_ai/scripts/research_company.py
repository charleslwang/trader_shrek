"""
Research a single company
"""

import sys
import uuid
from pathlib import Path
from datetime import datetime
import pandas as pd
from loguru import logger

# Add project python directory to path when running this script directly
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from shrek_ai.config import load_config, load_env
from shrek_ai.alpaca_data import AlpacaDataSource
from shrek_ai.filings import FilingManager
from shrek_ai.data_sources import DataSourceManager
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
from shrek_ai.multi_agent import MultiAgentDebater
from shrek_ai.math import (
    scenario_valuation,
    expected_return,
    downside,
    upside,
    upside_downside_ratio,
    margin_of_safety,
    piotroski_score,
    revision_score,
    timing_score,
    risk_penalty,
    shrek_score,
    update_scenario_probabilities,
)


def _compute_price_signals(bars_df) -> dict:
    """Compute price-derived proxy signals to use when LLM scores are missing."""
    if bars_df is None or len(bars_df) < 50:
        return {}
    close = bars_df['close'] if isinstance(bars_df, pd.DataFrame) else bars_df
    if hasattr(close, 'values'):
        prices = pd.Series(close.values)
    else:
        prices = pd.Series(close)

    current = float(prices.iloc[-1])
    sma50 = float(prices.iloc[-50:].mean())
    sma200 = float(prices.iloc[-200:].mean()) if len(prices) >= 200 else sma50
    high_52w = float(prices.max())
    low_52w = float(prices.min())
    returns = prices.pct_change().dropna()
    vol_20d = float(returns.iloc[-20:].std() * (252 ** 0.5)) if len(returns) >= 20 else 0.25

    # Quality proxy: trend strength (0.4 to 0.8)
    if sma200 > 0:
        trend_ratio = sma50 / sma200
        quality = max(0.0, min(1.0, 0.5 + (trend_ratio - 1.0) * 2.0))
    else:
        quality = 0.5

    # Timing proxies computed from actual prices
    trend_200d = 1.0 if current > sma200 else 0.0
    trend_50d = 1.0 if current > sma50 else 0.0
    # Relative strength vs 52w range
    if high_52w > low_52w:
        rs = (current - low_52w) / (high_52w - low_52w)
    else:
        rs = 0.5
    pullback = 1.0 if current >= high_52w * 0.95 else 0.5 if current >= high_52w * 0.90 else 0.0

    # Risk proxy from volatility
    risk_pen = min(1.0, vol_20d * 2.0)
    balance_sheet_risk = min(1.0, risk_pen * 0.8)
    valuation_risk = min(1.0, risk_pen * 1.0)
    volatility_risk = min(1.0, risk_pen * 1.1)
    thesis_fragility = 0.3 if trend_200d > 0.5 else 0.5
    accounting_risk = 0.15
    dilution_risk = 0.2
    llm_red_flag_risk = 0.1

    # Revision proxy from recent momentum
    mom_20d = (current / float(prices.iloc[-20])) - 1 if len(prices) >= 20 else 0.0
    mom_60d = (current / float(prices.iloc[-60])) - 1 if len(prices) >= 60 else 0.0
    earnings_surprise = 0.5 + min(0.3, max(-0.3, mom_20d * 5))
    guidance_revision = 0.5 + min(0.3, max(-0.3, mom_60d * 3))
    revenue_acceleration = earnings_surprise
    margin_revision = guidance_revision

    return {
        'quality': quality,
        'trend_200d': trend_200d,
        'trend_50d': trend_50d,
        'relative_strength': rs,
        'pullback_quality': pullback,
        'volume_confirmation': 0.5,
        'risk_penalty': risk_pen,
        'balance_sheet_risk': balance_sheet_risk,
        'valuation_risk': valuation_risk,
        'dilution_risk': dilution_risk,
        'volatility_risk': volatility_risk,
        'thesis_fragility': thesis_fragility,
        'accounting_risk': accounting_risk,
        'llm_red_flag_risk': llm_red_flag_risk,
        'earnings_surprise': earnings_surprise,
        'guidance_revision': guidance_revision,
        'revenue_acceleration': revenue_acceleration,
        'margin_revision': margin_revision,
        'volatility': vol_20d,
        'current_price': current,
        'sma50': sma50,
        'sma200': sma200,
        'high_52w': high_52w,
        'low_52w': low_52w,
    }


def research_company(symbol: str):
    """Research a single company"""
    load_env()
    config = load_config()
    symbol = symbol.upper().strip()
    
    logger.info(f"Researching {symbol}")
    
    # Initialize components
    alpaca_data = AlpacaDataSource()
    filing_manager = FilingManager(Path('data/filings'))
    memory_system = MemorySystem(Path('data/memory'), config=config.memory)
    storage_manager = StorageManager(Path('data/storage'))
    data_source_manager = DataSourceManager(Path('data'))
    
    # Initialize multi-agent debater if enabled
    multi_agent_debater = None
    if config.multi_agent and config.multi_agent.enabled:
        multi_agent_debater = MultiAgentDebater(config.multi_agent)
        logger.info("Multi-agent debate system enabled")
    
    # Initialize agents
    filing_analyst = FilingAnalyst()
    earnings_analyst = EarningsAnalyst()
    valuation_analyst = ValuationAnalyst()
    risk_analyst = RiskAnalyst()
    timing_analyst = TimingAnalyst()
    portfolio_manager = PortfolioManager()
    
    # Gather comprehensive data from ALL sources
    logger.info(f"Gathering comprehensive data for {symbol} from all sources...")
    comprehensive_data = data_source_manager.gather_company_data(
        symbol=symbol,
        company_name='',  # Could be populated from a mapping
        include_transcripts=True,
        include_news=True,
        include_ir=True,
        include_research=True,
        include_alternative=True,
        news_days=60,  # Extended to catch more events
        transcript_quarters=4,
    )
    
    # Save comprehensive data
    data_source_manager.save_company_data(symbol, comprehensive_data)
    
    # Extract consolidated text for agent prompts
    additional_context = {
        'comprehensive_data': comprehensive_data.get('consolidated', {}),
        'transcript_text': comprehensive_data.get('consolidated', {}).get('transcript_text', ''),
        'news_text': comprehensive_data.get('consolidated', {}).get('news_text', ''),
        'ir_text': comprehensive_data.get('consolidated', {}).get('ir_text', ''),
        'research_text': comprehensive_data.get('consolidated', {}).get('research_text', ''),
        'alternative_text': comprehensive_data.get('consolidated', {}).get('alternative_text', ''),
        'news_events': comprehensive_data.get('consolidated', {}).get('news_events', []),
        'analyst_consensus': comprehensive_data.get('consolidated', {}).get('analyst_consensus', {}),
        'bullish_theses': comprehensive_data.get('consolidated', {}).get('bullish_theses', []),
        'bearish_theses': comprehensive_data.get('consolidated', {}).get('bearish_theses', []),
        'alternative_signals': comprehensive_data.get('consolidated', {}).get('alternative_signals', []),
    }
    
    logger.info(f"Data sources summary:\n{data_source_manager.get_source_summary(comprehensive_data)}")
    
    # Get current price
    quote = alpaca_data.get_latest_quote(symbol)
    bid = float(quote['bid'])
    ask = float(quote['ask'])
    current_price = (bid + ask) / 2
    if current_price <= 0:
        raise ValueError(f"Invalid current price for {symbol}: bid={bid}, ask={ask}")
    
    # Get price history for timing
    bars = alpaca_data.get_bars(symbol, timeframe='day', limit=252)

    # Compute price-derived proxy signals for use when LLM data is missing
    price_signals = _compute_price_signals(bars)

    # Download filings
    filing_manager.download_filings(symbol, ['10-K', '10-Q', '8-K'], count=5)
    
    # Get latest 10-K
    tenk = filing_manager.get_latest_10k(symbol)
    
    # Get latest 10-Qs
    tenqs = filing_manager.get_latest_10q(symbol, count=4)
    
    # Build enriched context for agents
    enriched_context = {
        'transcript_summary': additional_context['transcript_text'][:15000] if additional_context['transcript_text'] else '',
        'news_summary': additional_context['news_text'][:10000] if additional_context['news_text'] else '',
        'ir_summary': additional_context['ir_text'][:10000] if additional_context['ir_text'] else '',
        'research_summary': additional_context['research_text'][:8000] if additional_context['research_text'] else '',
        'alternative_summary': additional_context['alternative_text'][:5000] if additional_context['alternative_text'] else '',
        'news_events': additional_context['news_events'][:15] if additional_context['news_events'] else [],
        'analyst_consensus': additional_context['analyst_consensus'],
        'bullish_theses': additional_context['bullish_theses'][:5],
        'bearish_theses': additional_context['bearish_theses'][:5],
        'alternative_signals': additional_context['alternative_signals'][:5],
    }
    
    filing_analysis = None
    thesis_events = []
    # Run filing analysis (with transcripts and news as additional context)
    if tenk:
        filing_analysis = filing_analyst.analyze_filing(
            symbol=symbol,
            filing_type='10-K',
            fiscal_period='FY',
            filing_content=tenk['content'],
            additional_context=enriched_context,
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
    
    # Run earnings analysis on transcripts
    transcript_text = additional_context['transcript_text']
    if transcript_text:
        earnings_analysis = earnings_analyst.analyze_earnings(
            symbol=symbol,
            fiscal_period='Recent Quarters',
            earnings_release=transcript_text[:8000],
            transcript=transcript_text[8000:15000] if len(transcript_text) > 8000 else '',
            additional_context=enriched_context,
        )
    else:
        earnings_analysis = None
    
    # Build price-derived financial data for valuation/risk agents when filings are unavailable
    price_financial_data = {
        'current_price': price_signals.get('current_price', current_price),
        'sma_50d': price_signals.get('sma50', current_price),
        'sma_200d': price_signals.get('sma200', current_price),
        'high_52w': price_signals.get('high_52w', current_price),
        'low_52w': price_signals.get('low_52w', current_price),
        'annualized_volatility': price_signals.get('volatility', 0.25),
    }

    # Run valuation analysis (with research and IR context)
    valuation_analysis = valuation_analyst.analyze_valuation(
        symbol=symbol,
        financial_data=price_financial_data,
        peer_data=None,
        historical_data=None,
        additional_context=enriched_context,
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
    
    # Run risk analysis (with news, research, and alternative data)
    news_articles = comprehensive_data.get('sources', {}).get('news', [])
    news_items = [a['title'] + ' ' + a.get('summary', '') for a in news_articles[:20]]
    risk_analysis = risk_analyst.analyze_risk(
        symbol=symbol,
        financial_data=price_financial_data,
        filing_analysis=filing_analysis if tenk else None,
        news=news_items,
        additional_context=enriched_context,
    )

    risk_score = risk_analyst.calculate_risk_score(risk_analysis)

    # Compute technical indicators from bars for timing analyst
    technical_indicators = {
        'sma_50d': price_signals.get('sma50'),
        'sma_200d': price_signals.get('sma200'),
        'high_52w': price_signals.get('high_52w'),
        'low_52w': price_signals.get('low_52w'),
        'annualized_volatility': price_signals.get('volatility'),
    }

    # Run timing analysis
    timing_analysis = timing_analyst.analyze_timing(
        symbol=symbol,
        price_data={'current_price': current_price, 'history': bars.to_dict('records')},
        technical_indicators=technical_indicators,
    )
    
    # Calculate mathematical scores
    # Extract scores from LLM analyses where available, else use neutral defaults
    def _safe_score(d: dict, *keys, default=0.5):
        for k in keys:
            if isinstance(d, dict) and k in d:
                v = d[k]
                if isinstance(v, (int, float)):
                    return max(0.0, min(1.0, float(v)))
            d = d.get(k, {}) if isinstance(d, dict) else {}
        return default

    def _safe_float(d: dict, *keys, default=0.0):
        for k in keys:
            if isinstance(d, dict) and k in d:
                v = d[k]
                if isinstance(v, (int, float)):
                    return float(v)
            d = d.get(k, {}) if isinstance(d, dict) else {}
        return default

    # Quality: try filing_analysis -> quality_metrics, else price-derived trend proxy
    quality = _safe_score(
        filing_analysis or {}, 'quality_metrics', 'overall',
        default=price_signals.get('quality', 0.65)
    ) if filing_analysis else price_signals.get('quality', 0.65)

    # Revision: try earnings_analysis, else price-momentum proxy
    revision = revision_score(
        earnings_surprise=_safe_score(earnings_analysis or {}, 'earnings_surprise_score', default=price_signals.get('earnings_surprise', 0.5)),
        guidance_revision=_safe_score(earnings_analysis or {}, 'guidance_revision_score', default=price_signals.get('guidance_revision', 0.5)),
        revenue_acceleration=_safe_score(earnings_analysis or {}, 'revenue_acceleration_score', default=price_signals.get('revenue_acceleration', 0.5)),
        margin_revision=_safe_score(earnings_analysis or {}, 'margin_revision_score', default=price_signals.get('margin_revision', 0.5)),
        llm_event=_safe_score(filing_analysis or {}, 'event_score', default=0.5),
    )

    # Timing: try timing_analysis, else price-derived timing proxy
    timing = timing_score(
        trend_200d=_safe_score(timing_analysis or {}, 'trend_200d_score', default=price_signals.get('trend_200d', 0.5)),
        trend_50d=_safe_score(timing_analysis or {}, 'trend_50d_score', default=price_signals.get('trend_50d', 0.5)),
        relative_strength=_safe_score(timing_analysis or {}, 'relative_strength_score', default=price_signals.get('relative_strength', 0.5)),
        pullback_quality=_safe_score(timing_analysis or {}, 'pullback_quality_score', default=price_signals.get('pullback_quality', 0.5)),
        volume_confirmation=_safe_score(timing_analysis or {}, 'volume_confirmation_score', default=price_signals.get('volume_confirmation', 0.5)),
    )

    # Risk: try risk_analysis, else price-derived volatility proxy
    risk_pen = risk_penalty(
        balance_sheet_risk=_safe_score(risk_analysis or {}, 'balance_sheet_risk', default=price_signals.get('balance_sheet_risk', 0.3)),
        valuation_risk=_safe_score(risk_analysis or {}, 'valuation_risk', default=price_signals.get('valuation_risk', 0.3)),
        dilution_risk=_safe_score(risk_analysis or {}, 'dilution_risk', default=price_signals.get('dilution_risk', 0.2)),
        volatility_risk=_safe_score(risk_analysis or {}, 'volatility_risk', default=price_signals.get('volatility_risk', 0.3)),
        thesis_fragility=_safe_score(risk_analysis or {}, 'thesis_fragility', default=price_signals.get('thesis_fragility', 0.2)),
        accounting_risk=_safe_score(risk_analysis or {}, 'accounting_risk', default=price_signals.get('accounting_risk', 0.1)),
        llm_red_flag_risk=_safe_score(risk_analysis or {}, 'llm_red_flag_risk', default=price_signals.get('llm_red_flag_risk', 0.1)),
    )

    # Piotroski: accept raw 0-9 F-score if present, else neutral/high-quality default
    raw_f_score = _safe_float(filing_analysis or {}, 'piotroski_f_score', default=7.0)
    piotroski = piotroski_score(int(max(0, min(9, round(raw_f_score)))))

    # Thesis probability: start at 0.70, adjust based on evidence
    thesis_probability = 0.70
    if earnings_analysis:
        # Boost/cut based on earnings surprise and guidance
        earnings_surprise = _safe_score(earnings_analysis, 'earnings_surprise_score', default=price_signals.get('earnings_surprise', 0.5))
        guidance_stance = earnings_analysis.get('guidance_stance', 'neutral') if isinstance(earnings_analysis, dict) else 'neutral'
        if guidance_stance in ['strong raise', 'moderate raise']:
            thesis_probability = min(0.95, thesis_probability + 0.10)
        elif guidance_stance in ['moderate cut', 'severe cut']:
            thesis_probability = max(0.50, thesis_probability - 0.15)
        elif earnings_surprise > 0.7:
            thesis_probability = min(0.95, thesis_probability + 0.05)
        elif earnings_surprise < 0.3:
            thesis_probability = max(0.50, thesis_probability - 0.05)

    if risk_analysis:
        # Cut if high severity risks found
        red_flags = risk_analysis.get('red_flags', []) if isinstance(risk_analysis, dict) else []
        high_severity = sum(1 for r in red_flags if isinstance(r, dict) and r.get('severity') == 'high')
        if high_severity >= 2:
            thesis_probability = max(0.50, thesis_probability - 0.10)

    p_bear, p_base, p_bull = update_scenario_probabilities(thesis_probability)

    exp_return = expected_return(v_bear, v_base, v_bull, current_price, p_bear, p_base, p_bull)
    down = downside(v_bear, current_price)
    up = upside(v_base, current_price)
    ud_ratio = upside_downside_ratio(up, down)
    mos = margin_of_safety(v_base, current_price)
    
    # Extract conviction scores from analyses
    secular_conviction = _safe_score(
        filing_analysis or {},
        'secular_thesis',
        'secular_conviction_score',
        default=0.0,
    )
    narrative_conviction = _safe_score(
        valuation_analysis or {},
        'narrative_valuation',
        'narrative_conviction_score',
        default=0.0,
    )
    
    shrek = shrek_score(
        expected_return_score=min(1.0, max(0.0, (exp_return - 0.05) / 0.35)),
        quality=quality,
        revision=revision,
        timing=timing,
        risk_penalty=risk_pen,
        secular_conviction=secular_conviction,
    )
    
    # Run portfolio manager (or multi-agent debate if enabled)
    if multi_agent_debater:
        # Build context for multi-agent debate
        context = f"""
Symbol: {symbol}
Current Price: ${current_price:.2f}

Valuation Analysis:
- Bear Case: ${v_bear:.2f}
- Base Case: ${v_base:.2f}
- Bull Case: ${v_bull:.2f}
- Expected Return: {exp_return:.2%}
- Upside/Downside Ratio: {ud_ratio:.2f}
- Margin of Safety: {mos:.2%}

Quality Metrics:
- Quality Score: {quality:.2f}
- Piotroski Score: {piotroski:.2f}
- Revision Score: {revision:.2f}

Risk Analysis:
- Risk Penalty: {risk_pen:.2f}

Timing Analysis:
- Timing Score: {timing:.2f}

Secular Thesis:
- Secular Conviction Score: {secular_conviction:.2f}
- Narrative Conviction Score: {narrative_conviction:.2f}

Filing Analysis: {filing_analysis if tenk else 'Not available'}
"""
        
        # Run multi-agent debate
        debate_result = multi_agent_debater.debate_decision(
            context=context,
            decision_type='investment_recommendation',
            additional_context={
                'symbol': symbol,
                'mathematical_scores': {
                    'expected_return': exp_return,
                    'upside_downside': ud_ratio,
                    'quality': quality,
                    'risk_penalty': risk_pen,
                    'thesis_probability': thesis_probability,
                    'timing': timing,
                    'secular_conviction': secular_conviction,
                    'narrative_conviction': narrative_conviction,
                }
            }
        )
        
        # Log debate
        multi_agent_debater.log_debate(debate_result, 'investment_recommendation', symbol)
        
        # Extract decision from debate result
        if debate_result.final_decision and debate_result.final_decision.get('action'):
            decision = {
                'decision': debate_result.final_decision['action'].upper(),
                'confidence': debate_result.final_decision.get('confidence', 0.5),
                'reasoning': debate_result.reasoning,
                'consensus_score': debate_result.consensus_score,
                'debate_rounds': debate_result.rounds,
                'multi_agent': True
            }
        else:
            # Fallback to portfolio manager
            decision = portfolio_manager.make_decision(
                symbol=symbol,
                filing_analysis=filing_analysis if tenk else None,
                earnings_analysis=earnings_analysis,
                valuation_analysis=valuation_analysis,
                risk_analysis=risk_analysis,
                timing_analysis=timing_analysis,
                mathematical_scores={
                    'expected_return': exp_return,
                    'upside_downside': ud_ratio,
                    'quality': quality,
                    'risk_penalty': risk_pen,
                    'thesis_probability': thesis_probability,
                    'timing': timing,
                    'secular_conviction': secular_conviction,
                    'narrative_conviction': narrative_conviction,
                },
            )
            decision['multi_agent'] = False
    else:
        # Run portfolio manager (single-agent mode)
        decision = portfolio_manager.make_decision(
            symbol=symbol,
            filing_analysis=filing_analysis if tenk else None,
            earnings_analysis=earnings_analysis,
            valuation_analysis=valuation_analysis,
            risk_analysis=risk_analysis,
            timing_analysis=timing_analysis,
            mathematical_scores={
                'expected_return': exp_return,
                'upside_downside': ud_ratio,
                'quality': quality,
                'risk_penalty': risk_pen,
                'thesis_probability': thesis_probability,
                'timing': timing,
                'secular_conviction': secular_conviction,
                'narrative_conviction': narrative_conviction,
            },
        )
        decision['multi_agent'] = False
    
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
        'thesis_probability': thesis_probability,
        'quality_score': quality,
        'piotroski_score': piotroski,
        'revision_score': revision,
        'timing_score': timing,
        'risk_penalty': risk_pen,
        'shrek_score': shrek,
        'decision': str(decision.get('decision', 'AVOID')).upper(),
        'notional': 0.0,
        'order_sent': False,
        'rust_accept': False,
        'rust_reject_reason': None,
        'source_docs': 'filing_analysis,valuation_analysis,risk_analysis,timing_analysis',
        'memo_path': None,
        'multi_agent': decision.get('multi_agent', False),
        'consensus_score': decision.get('consensus_score', None),
        'debate_rounds': decision.get('debate_rounds', None),
        'decision_confidence': decision.get('confidence', None),
        'decision_reasoning': decision.get('reasoning', None),
        'secular_conviction': secular_conviction,
        'narrative_conviction': narrative_conviction,
        'is_conviction': decision.get('is_conviction', False),
    })
    
    logger.info(f"Research complete for {symbol}: {decision.get('decision')}")
    if decision.get('multi_agent'):
        consensus_score = decision.get('consensus_score')
        consensus_text = f"{consensus_score:.2f}" if isinstance(consensus_score, (int, float)) else "n/a"
        logger.info(
            f"Multi-agent decision: consensus={consensus_text}, "
            f"rounds={decision.get('debate_rounds', 'n/a')}"
        )
    
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
