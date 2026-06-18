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
from shrek_ai.decision_policy import BUY_DECISIONS, SELL_DECISIONS, validate_final_decision
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
        decision_id: str = None,
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
        decision_id = decision_id or str(uuid.uuid4())
        
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
        decision_record = decision.to_dict()
        symbol = decision_record['symbol']
        position = position_map.get(symbol)
        position_exists = position is not None
        metrics = {
            'expected_return': decision_record.get('expected_return'),
            'upside_downside': decision_record.get('upside_downside'),
            'quality': decision_record.get('quality_score'),
            'risk_penalty': decision_record.get('risk_penalty'),
            'thesis_probability': decision_record.get('thesis_probability'),
            'timing': decision_record.get('timing_score'),
            'shrek_score': decision_record.get('shrek_score'),
            'secular_conviction': decision_record.get('secular_conviction'),
            'narrative_conviction': decision_record.get('narrative_conviction'),
            # Older rows will not have explicit provenance columns; treat them
            # as medium confidence but still require the math gate.
            'valuation_confidence': decision_record.get('valuation_confidence', 0.65),
            'proxy_confidence': decision_record.get('proxy_confidence', 0.65),
        }
        validated = validate_final_decision(
            {
                'decision': decision_record.get('decision'),
                'confidence': decision_record.get('decision_confidence'),
                'reasoning': decision_record.get('decision_reasoning'),
                'is_conviction': decision_record.get('is_conviction', False),
            },
            metrics,
            position_exists=position_exists,
            config=config,
        )
        decision_type = validated['decision']

        if decision_type != decision_record.get('decision'):
            logger.warning(
                f"{symbol}: execution gate changed stored decision "
                f"{decision_record.get('decision')} to {decision_type}: "
                f"{validated.get('deterministic_gate_reason')}"
            )
        
        is_buy = decision_type in BUY_DECISIONS
        is_sell = decision_type in SELL_DECISIONS
        
        if not is_buy and not is_sell:
            logger.info(f"{symbol}: {decision_type} is not actionable; skipping")
            continue
        
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
            # Determine conviction boost
            conviction_boost = 1.0
            if decision_type == 'CONVICTION_BUY' and validated.get('is_conviction'):
                conviction_boost = 1.5
                logger.info(f"Conviction buy for {symbol}: applying {conviction_boost}x boost")

            # Starter position with optional conviction boost and hard cap
            notional = starter_position_size(
                equity=equity,
                starter_position_pct=config.portfolio.starter_position_pct,
                expected_return=float(decision_record['expected_return']),
                quality=float(decision_record['quality_score']),
                risk_penalty=float(decision_record['risk_penalty']),
                thesis_probability=float(decision_record['thesis_probability']),
                upside_downside=float(decision_record['upside_downside']),
                conviction_boost=conviction_boost,
                max_single_position_pct=config.portfolio.max_single_position_pct,
            )

            if conviction_boost > 1.0:
                logger.info(f"Conviction buy for {symbol}: starter size ${notional:.2f}")
            
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
            raw_trim_notional = decision_record.get('notional')
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
                reason=f"{decision_type} decision from latest research (dated {decision_record['date']})",
                source_decision_path=f"data/decisions/{decision_record['decision_id']}.json",
                decision_id=str(decision_record['decision_id']),
            )
            
            if response.get('status') == 'accepted':
                logger.info(
                    f"Order accepted for {symbol}: "
                    f"order_id={response.get('order_id')}, "
                    f"client_order_id={response.get('client_order_id')}, "
                    f"broker_order_id={response.get('broker_order_id')}"
                )
                orders_sent += 1
                storage_manager.update_decision_execution(
                    str(decision_record['decision_id']),
                    order_sent=True,
                    rust_accept=True,
                    rust_reject_reason=None,
                )
            else:
                reason = response.get('reason', 'Unknown rejection')
                logger.warning(f"Order rejected for {symbol}: {reason}")
                storage_manager.update_decision_execution(
                    str(decision_record['decision_id']),
                    order_sent=True,
                    rust_accept=False,
                    rust_reject_reason=reason,
                )
        
        except Exception as e:
            logger.error(f"Failed to propose order for {symbol}: {e}")
            storage_manager.update_decision_execution(
                str(decision_record['decision_id']),
                order_sent=True,
                rust_accept=False,
                rust_reject_reason=str(e),
            )
    
    logger.info(f"Market hours executor complete. Sent {orders_sent} orders.")


if __name__ == '__main__':
    main()
