"""
Lightweight daily portfolio research for Shrek trading system

This script runs a fast daily check on current positions only:
1. Fetch recent news (last 7 days) for each position
2. Check for material events that might flip a decision
3. Run a lightweight risk/timing reassessment
4. Update decision if news warrants a change

Usage:
    python research_portfolio.py           # Research all current positions
    python research_portfolio.py --watchlist AAPL MSFT NVDA  # Also check watchlist
"""

import sys
import argparse
from pathlib import Path
from datetime import datetime
from loguru import logger

sys.path.insert(0, str(Path(__file__).parent.parent))

from shrek_ai.config import load_config, load_env, get_llm_config
from shrek_ai.alpaca_account import AlpacaAccount
from shrek_ai.alpaca_data import AlpacaDataSource
from shrek_ai.data_sources import DataSourceManager
from shrek_ai.storage import StorageManager
from shrek_ai.llm import LLMClient


PORTFOLIO_RESEARCH_PROMPT = """You are a portfolio risk monitor. Your job is to quickly assess whether any recent news or price action warrants changing a position decision.

Symbol: {symbol}
Current Price: ${current_price:.2f}
Entry Price: ${entry_price:.2f}
Unrealized P&L: {unrealized_pnl:.1%}
Position Value: ${market_value:.2f}

Last Full Research Decision: {last_decision}
Last Research Date: {last_date}
Expected Return (last): {expected_return:.1%}
Risk Penalty (last): {risk_penalty:.2f}
Quality Score (last): {quality:.2f}

Recent News (last 7 days):
{news_text}

Task:
1. Assess whether any recent news is MATERIAL to the investment thesis
2. If the stock is up significantly (>20% since entry), assess if valuation is stretched
3. If the stock is down significantly (<-15% since entry), assess if thesis is broken

Respond with valid JSON only:
{{
    "assessment": "HOLD" | "TRIM" | "SELL" | "RESEARCH", 
    "confidence": 0.0 to 1.0,
    "reasoning": "brief explanation",
    "material_events": ["list of material events if any"],
    "thesis_intact": true | false,
    "price_action_concern": "none" | "stretched" | "broken" | "monitor"
}}
"""


def load_last_decision(storage_manager: StorageManager, symbol: str) -> dict:
    """Load the most recent full research decision for a symbol"""
    decisions = storage_manager.get_decisions(symbol=symbol)
    if len(decisions) == 0:
        return None
    
    # Sort by date descending, take most recent
    decisions = decisions.sort_values('date', ascending=False)
    latest = decisions.iloc[0]
    
    return {
        'decision': latest.get('decision', 'AVOID'),
        'date': latest.get('date', 'N/A'),
        'expected_return': latest.get('expected_return', 0.0),
        'risk_penalty': latest.get('risk_penalty', 0.0),
        'quality_score': latest.get('quality_score', 0.0),
        'shrek_score': latest.get('shrek_score', 0.0),
        'upside_downside': latest.get('upside_downside', 0.0),
        'current_price_at_research': latest.get('current_price', 0.0),
    }


def lightweight_research(symbol: str, position: dict, storage_manager: StorageManager, llm_client: LLMClient):
    """Run lightweight research on a single position"""
    logger.info(f"Lightweight research for {symbol}")
    
    # Load last full decision
    last_decision = load_last_decision(storage_manager, symbol)
    if last_decision is None:
        logger.warning(f"No previous research found for {symbol}, skipping lightweight check")
        return None
    
    # Get current price
    alpaca_data = AlpacaDataSource()
    try:
        quote = alpaca_data.get_latest_quote(symbol)
        current_price = (quote['bid'] + quote['ask']) / 2
    except Exception as e:
        logger.warning(f"Could not get quote for {symbol}: {e}")
        current_price = position['current_price']
    
    # Fetch recent news only (last 7 days, lightweight)
    data_source_manager = DataSourceManager(Path('data'))
    try:
        news_data = data_source_manager.news.fetch_news(symbol, days=7, max_articles=15)
        news_text = "\n".join([
            f"- {a.get('title', '')}: {a.get('summary', '')[:200]}"
            for a in news_data.get('articles', [])[:10]
        ]) if news_data else "No recent news found."
    except Exception as e:
        logger.warning(f"News fetch failed for {symbol}: {e}")
        news_text = "News unavailable."
    
    # Build prompt
    prompt = PORTFOLIO_RESEARCH_PROMPT.format(
        symbol=symbol,
        current_price=current_price,
        entry_price=position['avg_entry_price'],
        unrealized_pnl=position['unrealized_plpc'],
        market_value=position['market_value'],
        last_decision=last_decision['decision'],
        last_date=last_decision['date'],
        expected_return=last_decision['expected_return'],
        risk_penalty=last_decision['risk_penalty'],
        quality=last_decision['quality_score'],
        news_text=news_text or "No recent news.",
    )
    
    # Run lightweight LLM check
    try:
        response = llm_client.generate(prompt, require_json=True, max_tokens=800)
        import json
        assessment = json.loads(response)
    except Exception as e:
        logger.error(f"LLM assessment failed for {symbol}: {e}")
        return None
    
    assessment['symbol'] = symbol
    assessment['current_price'] = current_price
    assessment['last_decision'] = last_decision['decision']
    assessment['last_date'] = last_decision['date']
    
    logger.info(
        f"{symbol}: assessment={assessment['assessment']}, "
        f"confidence={assessment.get('confidence', 0):.2f}, "
        f"thesis_intact={assessment.get('thesis_intact', True)}"
    )
    
    # If assessment says RESEARCH, trigger a full research
    if assessment['assessment'] == 'RESEARCH':
        logger.info(f"{symbol}: News suggests full re-research needed")
        from shrek_ai.scripts.research_company import research_company
        try:
            research_company(symbol)
            return {"action": "full_research_triggered", "symbol": symbol}
        except Exception as e:
            logger.error(f"Full research failed for {symbol}: {e}")
    
    # If assessment changes from BUY to SELL/TRIM, update the stored decision
    if assessment['assessment'] in ['SELL', 'TRIM'] and last_decision['decision'] in ['BUY_STARTER', 'ADD', 'CONVICTION_BUY', 'HOLD']:
        logger.info(f"{symbol}: Decision flipped from {last_decision['decision']} to {assessment['assessment']}")
        
        # Update stored decision
        decisions = storage_manager.get_decisions(symbol=symbol)
        if len(decisions) > 0:
            latest = decisions.sort_values('date', ascending=False).iloc[0]
            updated_decision = latest.to_dict()
            updated_decision['decision'] = assessment['assessment']
            updated_decision['date'] = datetime.now().date().isoformat()
            updated_decision['decision_reasoning'] = assessment.get('reasoning', 'Flipped by daily portfolio check')
            updated_decision['lightweight_update'] = True
            storage_manager.save_decision(updated_decision)
    
    return assessment


def main():
    parser = argparse.ArgumentParser(description="Lightweight portfolio research")
    parser.add_argument('--watchlist', nargs='+', default=[], help='Additional symbols to check')
    parser.add_argument('--force-full', action='store_true', help='Trigger full research instead of lightweight')
    args = parser.parse_args()
    
    load_env()
    config = load_config()
    llm_config = get_llm_config()
    
    logger.info("=== Starting Lightweight Portfolio Research ===")
    
    # Get current positions
    alpaca_account = AlpacaAccount()
    try:
        positions = alpaca_account.get_positions()
    except Exception as e:
        logger.error(f"Could not fetch positions: {e}")
        positions = []
    
    portfolio_symbols = [p['symbol'] for p in positions]
    
    # Add watchlist
    all_symbols = list(set(portfolio_symbols + args.watchlist))
    
    if not all_symbols:
        logger.info("No positions or watchlist symbols to research")
        return
    
    logger.info(f"Checking {len(all_symbols)} symbols: {all_symbols}")
    
    # Initialize LLM client (uses config from shrek.paper.yaml)
    llm_client = LLMClient(
        runtime=config.llm.runtime,
        model=config.llm.model,
        base_url=config.llm.base_url or llm_config.get('base_url', 'http://localhost:11434'),
    )
    
    storage_manager = StorageManager(Path('data/storage'))
    
    results = []
    
    for symbol in all_symbols:
        # Find position data if it exists
        position = next((p for p in positions if p['symbol'] == symbol), None)
        
        if position is None:
            # Watchlist symbol without a position
            position = {
                'symbol': symbol,
                'avg_entry_price': 0.0,
                'current_price': 0.0,
                'market_value': 0.0,
                'unrealized_plpc': 0.0,
            }
        
        if args.force_full:
            logger.info(f"{symbol}: Running full research (force-full flag)")
            from shrek_ai.scripts.research_company import research_company
            try:
                research_company(symbol)
                results.append({"symbol": symbol, "action": "full_research"})
            except Exception as e:
                logger.error(f"Full research failed for {symbol}: {e}")
                results.append({"symbol": symbol, "action": "failed", "error": str(e)})
        else:
            try:
                result = lightweight_research(symbol, position, storage_manager, llm_client)
                results.append(result)
            except Exception as e:
                logger.error(f"Lightweight research failed for {symbol}: {e}")
                results.append({"symbol": symbol, "action": "failed", "error": str(e)})
    
    # Summary
    logger.info("=== Portfolio Research Complete ===")
    
    sell_trim = [r for r in results if r and r.get('assessment') in ['SELL', 'TRIM']]
    full_research = [r for r in results if r and r.get('action') == 'full_research_triggered']
    
    if sell_trim:
        logger.info(f"SELL/TRIM signals: {len(sell_trim)}")
        for r in sell_trim:
            logger.info(f"  {r['symbol']}: {r['assessment']} (confidence: {r.get('confidence', 0):.2f})")
    
    if full_research:
        logger.info(f"Full research triggered: {len(full_research)}")
        for r in full_research:
            logger.info(f"  {r['symbol']}")
    
    if not sell_trim and not full_research:
        logger.info("All positions: HOLD. No action needed.")


if __name__ == '__main__':
    main()
