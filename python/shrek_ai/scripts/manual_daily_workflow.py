"""
Manual daily workflow for BlueShrek trading system

Weekly workflow (full deep research):
    python manual_daily_workflow.py --research    # Full research on all candidates

Daily workflow (lightweight portfolio check + execute):
    python manual_daily_workflow.py --portfolio   # Check positions + send orders

One-off commands:
    python manual_daily_workflow.py --execute     # Execute orders only
    python manual_daily_workflow.py --status      # Show current status
"""

import sys
import argparse
from pathlib import Path
from loguru import logger

from shrek_ai.config import load_config, load_env
from shrek_ai.storage import StorageManager
from shrek_ai.alpaca_account import AlpacaAccount


def run_full_research():
    """Run full research on all candidates (weekly deep dive)"""
    logger.info("=== Running Full Research (Weekly) ===")
    
    from shrek_ai.scripts.run_daily_research import main as research_main
    research_main()


def run_portfolio_research():
    """Run lightweight research on current positions only (daily check)"""
    logger.info("=== Running Portfolio Research (Daily) ===")
    
    from shrek_ai.scripts.research_portfolio import main as portfolio_main
    portfolio_main()


def execute_orders():
    """Execute orders based on today's research"""
    logger.info("=== Executing Orders ===")
    
    from shrek_ai.scripts.run_market_hours_executor import main as execute_main
    execute_main()


def show_status():
    """Show current status - latest research for each symbol"""
    load_env()
    
    storage_manager = StorageManager(Path('data/storage'))
    alpaca_account = AlpacaAccount()
    
    import math
    
    def safe_float(value, default=0.0):
        """Convert API values to finite floats."""
        try:
            parsed = float(value)
            return parsed if math.isfinite(parsed) else default
        except (TypeError, ValueError):
            return default
    
    # Get latest decisions for each symbol (regardless of date)
    latest_decisions = storage_manager.get_latest_decisions()
    
    logger.info(f"=== Status (latest research across all dates) ===")
    logger.info(f"Total symbols with research: {len(latest_decisions)}")
    
    if len(latest_decisions) > 0:
        logger.info("\nDecisions by type:")
        for decision_type in latest_decisions['decision'].unique():
            count = len(latest_decisions[latest_decisions['decision'] == decision_type])
            logger.info(f"  {decision_type}: {count}")
        
        logger.info("\nLatest BUY decisions:")
        buy_decisions = latest_decisions[latest_decisions['decision'].str.contains('BUY', na=False)]
        for _, row in buy_decisions.iterrows():
            date_str = row.get('date', 'N/A')
            conf = row.get('decision_confidence', 'N/A')
            logger.info(f"  {row['symbol']}: {row['decision']} (date: {date_str}, confidence: {conf})")
        
        logger.info("\nLatest SELL/TRIM decisions:")
        sell_decisions = latest_decisions[latest_decisions['decision'].isin(['SELL', 'TRIM'])]
        for _, row in sell_decisions.iterrows():
            date_str = row.get('date', 'N/A')
            logger.info(f"  {row['symbol']}: {row['decision']} (date: {date_str})")
    
    # Get current positions
    try:
        positions = alpaca_account.get_positions()
        logger.info(f"\nCurrent positions: {len(positions)}")
        for pos in positions:
            qty = safe_float(pos.get('qty'))
            avg_price = safe_float(pos.get('avg_entry_price'))
            logger.info(f"  {pos['symbol']}: {qty} shares @ ${avg_price:.2f}")
    except Exception as e:
        logger.warning(f"Could not fetch positions: {e}")
    
    # Research database stats
    all_decisions = storage_manager.get_decisions()
    logger.info(f"\nResearch database: {len(all_decisions)} total decisions stored")
    if len(all_decisions) > 0:
        logger.info(f"Date range: {all_decisions['date'].min()} to {all_decisions['date'].max()}")


def main():
    parser = argparse.ArgumentParser(description="Manual daily workflow for Shrek")
    parser.add_argument('--research', action='store_true', help='Full research on all candidates (weekly)')
    parser.add_argument('--portfolio', action='store_true', help='Lightweight portfolio research + execute (daily)')
    parser.add_argument('--execute', action='store_true', help='Execute orders only')
    parser.add_argument('--status', action='store_true', help='Show status only')
    parser.add_argument('--full', action='store_true', help='Run full research, then execute orders')
    
    args = parser.parse_args()
    
    # Default to portfolio mode if no args (daily routine)
    if not any([args.research, args.portfolio, args.execute, args.status, args.full]):
        args.portfolio = True
    
    if args.status:
        show_status()
    elif args.research:
        run_full_research()
    elif args.portfolio:
        run_portfolio_research()
        execute_orders()
    elif args.execute:
        execute_orders()
    elif args.full:
        run_full_research()
        execute_orders()


if __name__ == '__main__':
    main()
