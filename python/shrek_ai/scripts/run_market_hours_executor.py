"""
Run market hours executor - send order proposals to Rust daemon
"""

import sys
import uuid
import requests
from pathlib import Path
from loguru import logger

# Add project python directory to path when running this script directly
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

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
        response.raise_for_status()
        
        return response.json()
    
    def cancel_all_orders(self) -> dict:
        """Cancel all orders"""
        response = requests.post(
            f"{self.base_url}/orders/cancel_all",
            timeout=30,
        )
        response.raise_for_status()
        return response.json()
    
    def refresh_positions(self) -> dict:
        """Refresh positions"""
        response = requests.post(
            f"{self.base_url}/positions/refresh",
            timeout=30,
        )
        response.raise_for_status()
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
    equity = float(account['equity'])
    
    logger.info(f"Account equity: ${equity:,.2f}")
    
    # Get current positions
    positions = alpaca_account.get_positions()
    position_map = {p['symbol']: p for p in positions}
    
    # Get latest decisions for each symbol (most recent research regardless of date)
    decisions_df = storage_manager.get_latest_decisions()
    
    logger.info(f"Found {len(decisions_df)} latest decisions across all dates")
    
    # Process each decision
    orders_sent = 0
    max_new_buys = config.portfolio.max_new_buys_per_day
    max_sells = config.portfolio.max_sells_per_day
    new_buys_sent = 0
    sells_sent = 0
    
    for _, decision in decisions_df.iterrows():
        symbol = decision['symbol']
        decision_type = decision['decision']
        
        # Check if this is a buy or sell decision
        is_buy = decision_type in ['BUY_STARTER', 'ADD', 'CONVICTION_BUY']
        is_sell = decision_type in ['SELL', 'TRIM']
        
        if not is_buy and not is_sell:
            continue
        
        # Check if position exists
        position = position_map.get(symbol)
        
        # Get current price
        try:
            quote = alpaca_account.api.get_latest_quote(symbol)
            ask_price = float(quote.ap)
            bid_price = float(quote.bp)
            current_price = (ask_price + bid_price) / 2
        except Exception as e:
            logger.warning(f"Could not get quote for {symbol}: {e}, skipping")
            continue
        
        # Calculate order notional
        if decision_type in ['BUY_STARTER', 'CONVICTION_BUY']:
            # Starter position (conviction buys get same starter sizing but with higher conviction)
            notional = starter_position_size(
                equity=equity,
                starter_position_pct=config.portfolio.starter_position_pct,
                expected_return=float(decision['expected_return']),
                quality=float(decision['quality_score']),
                risk_penalty=float(decision['risk_penalty']),
                thesis_probability=float(decision['thesis_probability']),
                upside_downside=float(decision['upside_downside']),
            )
            
            # For conviction buys, consider larger starter if thesis is strong
            if decision_type == 'CONVICTION_BUY' and decision.get('is_conviction'):
                # Increase starter by 50% for conviction (7.5% instead of 5%)
                notional = min(notional * 1.5, equity * config.portfolio.starter_position_pct * 1.5)
                logger.info(f"Conviction buy for {symbol}: increased starter to ${notional:.2f}")
            
            # Check max new buys
            if new_buys_sent >= max_new_buys:
                logger.warning(f"Max new buys ({max_new_buys}) reached, skipping {symbol}")
                continue
            
            new_buys_sent += 1
            side = "buy"
            limit_price = current_price * (1 - config.orders.limit_buy_discount_bps / 10000)
        
        elif decision_type == 'ADD':
            # Add to existing position
            if position is None:
                logger.warning(f"ADD decision for {symbol} but no position exists, skipping")
                continue
            
            current_position_value = float(position['market_value'])
            target_position_value = equity * config.portfolio.normal_position_pct
            
            notional = add_position_size(
                equity=equity,
                normal_position_pct=config.portfolio.normal_position_pct,
                current_position_value=current_position_value,
                target_position_value=target_position_value,
            )
            
            side = "buy"
            limit_price = current_price * (1 - config.orders.limit_buy_discount_bps / 10000)
        
        elif is_sell:
            # Sell or trim existing position
            if position is None:
                logger.warning(f"{decision_type} decision for {symbol} but no position exists, skipping")
                continue
            
            if sells_sent >= max_sells:
                logger.warning(f"Max sells ({max_sells}) reached, skipping {symbol}")
                continue
            
            sells_sent += 1
            
            position_market_value = float(position['market_value'])
            raw_trim_notional = decision.get('notional')
            trim_notional = float(raw_trim_notional) if raw_trim_notional is not None and raw_trim_notional == raw_trim_notional else position_market_value * 0.5
            notional = position_market_value if decision_type == 'SELL' else trim_notional
            side = "sell"
            limit_price = current_price * (1 + config.orders.limit_sell_premium_bps / 10000)
        
        # Skip if notional is too small
        if notional < 1.0:
            logger.info(f"Notional ${notional:.2f} too small for {symbol}, skipping")
            continue
        
        # Propose order to Rust daemon
        try:
            response = executor.propose_order(
                symbol=symbol,
                side=side,
                notional=notional,
                order_type="limit",
                limit_price=limit_price,
                time_in_force=config.orders.time_in_force,
                reason=f"{decision_type} decision from latest research (dated {decision['date']})",
                source_decision_path=f"data/decisions/{decision['decision_id']}.json",
            )
            
            if response.get('status') == 'accepted':
                logger.info(
                    f"Order accepted for {symbol}: "
                    f"order_id={response.get('order_id')}, "
                    f"client_order_id={response.get('client_order_id')}, "
                    f"broker_order_id={response.get('broker_order_id')}"
                )
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
