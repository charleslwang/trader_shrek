"""
Run daily research for all candidates
"""

import sys
import argparse
from pathlib import Path
from datetime import datetime
from loguru import logger

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from shrek_ai.config import load_config, load_env
from shrek_ai.storage import StorageManager
from shrek_ai.research_company import research_company


def main():
    """Run daily research for all candidates"""
    parser = argparse.ArgumentParser(description="Run deep research on candidates")
    parser.add_argument('--discover', action='store_true', help='Discover and research new candidates outside base list')
    parser.add_argument('--max-discovered', type=int, default=10, help='Max new candidates to discover')
    parser.add_argument('--add-threshold', type=float, default=0.75, help='Min Shrek score to auto-add discovered symbol')
    args = parser.parse_args()
    
    load_env()
    config = load_config()
    
    logger.info("Starting daily research")
    
    # Load candidates
    candidates_path = Path('data/candidates.txt')
    
    if not candidates_path.exists():
        logger.error("Candidates file not found. Run build_universe first.")
        sys.exit(1)
    
    with open(candidates_path, 'r') as f:
        candidates = [line.strip() for line in f if line.strip() and not line.strip().startswith('#')]
    
    logger.info(f"Base candidate list: {len(candidates)} symbols")
    
    # Check if research already done today
    storage_manager = StorageManager(Path('data/storage'))
    today = datetime.now().date().isoformat()
    
    existing_decisions = storage_manager.get_decisions(start_date=today, end_date=today)
    already_researched = set(existing_decisions['symbol'].unique()) if len(existing_decisions) > 0 else set()
    
    if already_researched:
        logger.info(f"Found {len(already_researched)} symbols already researched today")
    
    # Track symbols to research (base + discovered)
    symbols_to_research = candidates.copy()
    
    # --- DISCOVERY MODE ---
    if args.discover:
        from shrek_ai.discovery import CandidateDiscovery
        
        discovery = CandidateDiscovery(base_candidates_path=candidates_path)
        new_candidates = discovery.run_discovery(max_new_candidates=args.max_discovered)
        
        if new_candidates:
            new_symbols = [c['symbol'] for c in new_candidates]
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
        if symbol in already_researched:
            logger.info(f"Skipping {symbol} (already researched today)")
            continue
        
        try:
            logger.info(f"Researching {symbol}")
            decision = research_company(symbol)
            if decision:
                research_results[symbol] = decision
        except Exception as e:
            logger.error(f"Failed to research {symbol}: {e}")
            continue
    
    # --- POST-RESEARCH: Auto-add strong discovered candidates ---
    if args.discover and discovered_symbols:
        symbols_to_add = []
        
        for sym in discovered_symbols:
            if sym in research_results:
                result = research_results[sym]
                shrek = result.get('shrek_score', 0.0)
                decision = result.get('decision', 'AVOID')
                
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
    
    logger.info("Daily research complete")


if __name__ == '__main__':
    main()
