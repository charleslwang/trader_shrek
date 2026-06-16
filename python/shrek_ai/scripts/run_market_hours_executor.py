"""
Run market hours executor - send order proposals to Rust daemon
"""

import sys
import uuid
import requests
from pathlib import Path
from datetime import datetime
from loguru import logger

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from shrek_ai.config import load_config, load_env
from shrek_ai.storage import StorageManager
from shrek_ai.alpaca_account import AlpacaAccount
from shrek_ai.math import (
    starter_position_size,
    add_position_size,
)


class RustExecutor:
    """Client for Rust execution daemon"""
    
    def __init__(self, base_url: str = "http://127.0.0.1:8080"):
        self.base_url = base_url
    
    def health_check(self) -> bool:
        """Check if Rust daemon is healthy"""
        try:
            response = requests.get(f"{self.base_url}/health", timeout=5)
            return response.status_code == 200
        except requests.exceptions.RequestException:
            return False
    
    def propose_order(
        self,
        symbol: str,
        side: str,
        notional: float,
        order_type: str = "limit",
        limit_price: float = None,
        time_in_force: str = "day",
        reason: str = "",
        source_decision_path: str = "",
    ) -> dict:
        """
        Propose an order to Rust daemon.
        
        Args:
            symbol: Stock symbol
            side: Buy or sell
            notional: Order notional
            order_type: Order type
            limit_price: Limit price
            time_in_force: Time in force
            reason: Order reason
            source_decision_path: Path to decision memo
        
        Returns:
            Response from Rust daemon
        """
        decision_id = str(uuid.uuid4())
        
        payload = {
            "decision_id": decision_id,
            "symbol": symbol,
            "side": side.lower(),
            "notional": notional,
            "order_type": order_type.lower(),
            "limit_price": limit_price,
            "time_in_force": time_in_force.lower(),
            "reason": reason,
            "source_decision_path": source_decision_path,
        }
        
        response = requests.post(
            f"{self.base_url}/orders/propose",
            json=payload,
            timeout=30,
        )
        
        return response.json()
    
    def cancel_all_orders(self) -> dict:
        """Cancel all orders"""
        response = requests.post(
            f"{self.base_url}/orders/cancel_all",
            timeout=30,
        )
        return response.json()
    
    def refresh_positions(self) -> dict:
        """Refresh positions"""
        response = requests.post(
            f"{self.base_url}/positions/refresh",
            timeout=30,
        )
        return response.json()


def main():
    """Main entry point"""
    load_env()
    config = load_config()
    
    logger.info("Starting market hours executor")
    
    # Initialize components
    executor = RustExecutor()
    storage_manager = StorageManager(Path('data/storage'))
    alpaca_account = AlpacaAccount()
    
    # Check Rust daemon health
    if not executor.health_check():
        logger.error("Rust daemon is not healthy. Exiting.")
        sys.exit(1)
    
    # Get account info
    account = alpaca_account.get_account()
    equity = account['equity']
    
    logger.info(f"Account equity: ${equity:,.2f}")
    
    # Get current positions
    positions = alpaca_account.get_positions()
    position_map = {p['symbol']: p for p in positions}
    
    # Get today's decisions
    today = datetime.now().date().isoformat()
    decisions_df = storage_manager.get_decisions(start_date=today, end_date=today)
    
    logger.info(f"Found {len(decisions_df)} decisions for today")
    
    # Process each decision
    orders_sent = 0
    max_new_buys = config.portfolio.max_new_buys_per_day
    new_buys_sent = 0
    
    for _, decision in decisions_df.iterrows():
        symbol = decision['symbol']
        decision_type = decision['decision']
        
        # Skip if not a buy decision
        if decision_type not in ['BUY_STARTER', 'ADD']:
            continue
        
        # Check if position exists
        position = position_map.get(symbol)
        
        # Calculate order notional
        if decision_type == 'BUY_STARTER':
            # Starter position
            notional = starter_position_size(
                equity=equity,
                starter_position_pct=config.portfolio.starter_position_pct,
                expected_return=decision['expected_return'],
                quality=decision['quality_score'],
                risk_penalty=decision['risk_penalty'],
                thesis_probability=decision['thesis_probability'],
                upside_downside=decision['upside_downside'],
            )
            
            # Check max new buys
            if new_buys_sent >= max_new_buys:
                logger.warning(f"Max new buys ({max_new_buys}) reached, skipping {symbol}")
                continue
            
            new_buys_sent += 1
        
        elif decision_type == 'ADD':
            # Add to existing position
            if position is None:
                logger.warning(f"ADD decision for {symbol} but no position exists, skipping")
                continue
            
            current_position_value = position['market_value']
            target_position_value = equity * config.portfolio.normal_position_pct
            
            notional = add_position_size(
                equity=equity,
                normal_position_pct=config.portfolio.normal_position_pct,
                current_position_value=current_position_value,
                target_position_value=target_position_value,
            )
        
        # Skip if notional is too small
        if notional < 1.0:
            logger.info(f"Notional ${notional:.2f} too small for {symbol}, skipping")
            continue
        
        # Get current price
        quote = alpaca_account.api.get_latest_quote(symbol)
        current_price = (quote.ap + quote.bp) / 2
        
        # Calculate limit price
        if decision_type == 'BUY_STARTER':
            limit_price = current_price * (1 - config.orders.limit_buy_discount_bps / 10000)
        else:
            limit_price = current_price * (1 - config.orders.limit_buy_discount_bps / 10000)
        
        # Propose order to Rust daemon
        try:
            response = executor.propose_order(
                symbol=symbol,
                side="buy",
                notional=notional,
                order_type="limit",
                limit_price=limit_price,
                time_in_force=config.orders.time_in_force,
                reason=f"{decision_type} decision from daily research",
                source_decision_path=f"data/decisions/{decision['decision_id']}.json",
            )
            
            if response.get('status') == 'accepted':
                logger.info(f"Order accepted for {symbol}: {response.get('order_id')}")
                orders_sent += 1
                
                # Update decision in storage
                # (Would need update method in storage_manager)
            else:
                logger.warning(f"Order rejected for {symbol}: {response.get('reason')}")
        
        except Exception as e:
            logger.error(f"Failed to propose order for {symbol}: {e}")
    
    logger.info(f"Market hours executor complete. Sent {orders_sent} orders.")


if __name__ == '__main__':
    main()
