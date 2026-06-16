"""
Run daily research for all candidates
"""

import sys
from pathlib import Path
from loguru import logger

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from shrek_ai.config import load_config, load_env
from shrek_ai.research_company import research_company


def main():
    """Run daily research for all candidates"""
    load_env()
    config = load_config()
    
    logger.info("Starting daily research")
    
    # Load candidates
    candidates_path = Path('data/candidates.txt')
    
    if not candidates_path.exists():
        logger.error("Candidates file not found. Run build_universe first.")
        sys.exit(1)
    
    with open(candidates_path, 'r') as f:
        candidates = [line.strip() for line in f if line.strip()]
    
    logger.info(f"Researching {len(candidates)} candidates")
    
    # Research each candidate
    for symbol in candidates:
        try:
            research_company(symbol)
        except Exception as e:
            logger.error(f"Failed to research {symbol}: {e}")
            continue
    
    logger.info("Daily research complete")


if __name__ == '__main__':
    main()
