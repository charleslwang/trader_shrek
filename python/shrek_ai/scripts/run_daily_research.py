"""
Run daily research for all candidates
"""

import sys
import math
import argparse
from pathlib import Path
from datetime import datetime
from loguru import logger

# Add project python directory to path when running this script directly
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from shrek_ai.config import load_env
from shrek_ai.storage import StorageManager
from shrek_ai.scripts.research_company import research_company


def normalize_symbol(symbol: str) -> str:
    """Normalize ticker symbols from files, discovery, or storage."""
    return str(symbol).upper().strip()


def safe_float(value, default: float = 0.0) -> float:
    """Convert model/storage values into finite floats."""
    try:
        parsed = float(value)
        return parsed if math.isfinite(parsed) else default
    except (TypeError, ValueError):
        return default


def read_candidates(path: Path) -> list[str]:
    """Read, normalize, dedupe, and preserve order from candidates.txt."""
    seen = set()
    candidates = []
    with open(path, 'r') as f:
        for line in f:
            stripped = line.strip()
            if not stripped or stripped.startswith('#'):
                continue
            symbol = normalize_symbol(stripped)
            if symbol and symbol not in seen:
                seen.add(symbol)
                candidates.append(symbol)
    return candidates


def main():
    """Run daily research for all candidates"""
    parser = argparse.ArgumentParser(description="Run deep research on candidates")
    parser.add_argument('--discover', action='store_true', help='Discover and research new candidates outside base list')
    parser.add_argument('--max-discovered', type=int, default=10, help='Max new candidates to discover')
    parser.add_argument('--add-threshold', type=float, default=0.75, help='Min Shrek score to auto-add discovered symbol')
    args = parser.parse_args()
    
    load_env()
    
    logger.info("Starting daily research")
    
    # Load candidates
    candidates_path = Path('data/candidates.txt')
    
    if not candidates_path.exists():
        logger.error("Candidates file not found. Run build_universe first.")
        sys.exit(1)
    
    candidates = read_candidates(candidates_path)
    
    logger.info(f"Base candidate list: {len(candidates)} symbols")
    if not candidates:
        logger.warning("Candidates file is empty; nothing to research unless discovery finds new symbols")
    
    # Check if research already done today
    storage_manager = StorageManager(Path('data/storage'))
    today = datetime.now().date().isoformat()
    
    existing_decisions = storage_manager.get_decisions(start_date=today, end_date=today)
    already_researched = (
        {normalize_symbol(symbol) for symbol in existing_decisions['symbol'].dropna().unique()}
        if existing_decisions is not None and len(existing_decisions) > 0 and 'symbol' in existing_decisions.columns
        else set()
    )
    
    if already_researched:
        logger.info(f"Found {len(already_researched)} symbols already researched today")
    
    # Track symbols to research (base + discovered)
    symbols_to_research = list(candidates)
    
    # --- DISCOVERY MODE ---
    if args.discover:
        from shrek_ai.discovery import CandidateDiscovery
        
        discovery = CandidateDiscovery(base_candidates_path=candidates_path)
        new_candidates = discovery.run_discovery(max_new_candidates=args.max_discovered)
        
        if new_candidates:
            new_symbols = []
            seen_new = set(symbols_to_research)
            for candidate in new_candidates:
                symbol = normalize_symbol(candidate.get('symbol', '')) if isinstance(candidate, dict) else normalize_symbol(candidate)
                if symbol and symbol not in seen_new:
                    seen_new.add(symbol)
                    new_symbols.append(symbol)
            logger.info(f"Discovered {len(new_symbols)} new candidates: {new_symbols}")
            symbols_to_research.extend(new_symbols)
            
            # Auto-add to candidates.txt if they pass a strong threshold later
            # (we'll check after research)
            discovered_symbols = new_symbols
        else:
            discovered_symbols = []
    else:
        discovered_symbols = []
    
    # Research each candidate (skip if already done today)
    research_results = {}
    
    for symbol in symbols_to_research:
        symbol = normalize_symbol(symbol)
        if not symbol:
            continue
        if symbol in already_researched:
            logger.info(f"Skipping {symbol} (already researched today)")
            continue
        
        try:
            logger.info(f"Researching {symbol}")
            decision = research_company(symbol)
            if isinstance(decision, dict):
                decision['symbol'] = normalize_symbol(decision.get('symbol', symbol))
                research_results[symbol] = decision
            else:
                logger.warning(f"No structured decision returned for {symbol}")
        except Exception as e:
            logger.error(f"Failed to research {symbol}: {e}")
            continue
    
    # --- POST-RESEARCH: Auto-add strong discovered candidates ---
    if args.discover and discovered_symbols:
        symbols_to_add = []
        
        for sym in discovered_symbols:
            if sym in research_results:
                result = research_results[sym]
                shrek = safe_float(result.get('shrek_score', 0.0))
                decision = str(result.get('decision', 'AVOID')).upper()
                
                if shrek >= args.add_threshold and decision in ['BUY_STARTER', 'CONVICTION_BUY']:
                    logger.info(
                        f"Auto-adding {sym} to candidates.txt: "
                        f"shrek={shrek:.2f}, decision={decision}"
                    )
                    symbols_to_add.append(sym)
                else:
                    logger.info(
                        f"Not adding {sym}: shrek={shrek:.2f}, decision={decision} "
                        f"(threshold={args.add_threshold})"
                    )
        
        if symbols_to_add:
            discovery.add_to_candidates(symbols_to_add, reason="strong_research_signal")
    
    logger.info(
        f"Daily research complete: researched={len(research_results)}, "
        f"skipped_today={len(already_researched)}"
    )


if __name__ == '__main__':
    main()
