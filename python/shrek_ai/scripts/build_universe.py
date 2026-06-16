"""
Build trading universe from Alpaca
"""

import sys
from pathlib import Path
from loguru import logger

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from shrek_ai.config import load_config, load_env
from shrek_ai.alpaca_data import AlpacaDataSource


def main():
    """Build trading universe"""
    load_env()
    config = load_config()
    
    logger.info("Building trading universe")
    
    # Initialize Alpaca data source
    alpaca = AlpacaDataSource()
    
    # Build universe
    universe = alpaca.build_universe(
        min_price=config.universe.min_price,
        max_price=config.universe.max_price,
        min_market_cap=config.universe.min_market_cap,
        require_fractionable=config.universe.require_fractionable,
        require_tradable=config.universe.require_tradable,
        asset_class=config.universe.asset_class,
    )
    
    # Save universe to file
    output_path = Path('data/universe.txt')
    output_path.parent.mkdir(exist_ok=True)
    
    with open(output_path, 'w') as f:
        for symbol in universe:
            f.write(f"{symbol}\n")
    
    logger.info(f"Saved {len(universe)} symbols to {output_path}")
    
    # Limit to candidate limit per day
    candidate_symbols = universe[:config.universe.candidate_limit_per_day]
    
    output_path = Path('data/candidates.txt')
    with open(output_path, 'w') as f:
        for symbol in candidate_symbols:
            f.write(f"{symbol}\n")
    
    logger.info(f"Saved {len(candidate_symbols)} candidates to {output_path}")


if __name__ == '__main__':
    main()
