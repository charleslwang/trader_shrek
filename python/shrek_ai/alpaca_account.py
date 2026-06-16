"""
Alpaca account and position management
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
import pandas as pd
from alpaca_trade_api import REST
from loguru import logger

from .config import get_alpaca_config


class AlpacaAccount:
    """Alpaca account and position management"""
    
    def __init__(self):
        config = get_alpaca_config()
        self.api = REST(
            key_id=config['api_key'],
            secret_key=config['secret_key'],
            base_url=config['base_url'],
            api_version='v2'
        )
    
    def get_account(self) -> Dict[str, Any]:
        """Get account information"""
        account = self.api.get_account()
        return {
            'id': account.id,
            'account_number': account.account_number,
            'cash': float(account.cash),
            'portfolio_value': float(account.portfolio_value),
            'pattern_day_trader': account.pattern_day_trader,
            'trading_blocked': account.trading_blocked,
            'transfers_blocked': account.transfers_blocked,
            'account_blocked': account.account_blocked,
            'buying_power': float(account.buying_power),
            'daytrading_buying_power': float(account.daytrading_buying_power),
            'regt_buying_power': float(account.regt_buying_power),
            'equity': float(account.equity),
            'last_equity': float(account.last_equity),
            'long_market_value': float(account.long_market_value),
            'short_market_value': float(account.short_market_value),
            'initial_margin': float(account.initial_margin),
            'maintenance_margin': float(account.maintenance_margin),
            'last_maintenance_margin': float(account.last_maintenance_margin),
            'daytrading_buying_power': float(account.daytrading_buying_power),
            'regt_buying_power': float(account.regt_buying_power),
            'multiplier': account.multiplier,
        }
    
    def get_positions(self) -> List[Dict[str, Any]]:
        """Get all open positions"""
        positions = self.api.list_positions()
        return [
            {
                'symbol': p.symbol,
                'quantity': float(p.qty),
                'avg_entry_price': float(p.avg_entry_price),
                'current_price': float(p.current_price),
                'market_value': float(p.market_value),
                'cost_basis': float(p.cost_basis),
                'unrealized_pl': float(p.unrealized_pl),
                'unrealized_plpc': float(p.unrealized_plpc),
                'side': p.side,
                'asset_margin': float(p.asset_margin),
            }
            for p in positions
        ]
    
    def get_position(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get position for a specific symbol"""
        try:
            position = self.api.get_position(symbol)
            return {
                'symbol': position.symbol,
                'quantity': float(position.qty),
                'avg_entry_price': float(position.avg_entry_price),
                'current_price': float(position.current_price),
                'market_value': float(position.market_value),
                'cost_basis': float(position.cost_basis),
                'unrealized_pl': float(position.unrealized_pl),
                'unrealized_plpc': float(position.unrealized_plpc),
                'side': position.side,
            }
        except Exception as e:
            logger.warning(f"No position found for {symbol}: {e}")
            return None
    
    def get_orders(
        self,
        status: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Get orders"""
        orders = self.api.list_orders(
            status=status,
            limit=limit,
        )
        return [
            {
                'id': o.id,
                'client_order_id': o.client_order_id,
                'symbol': o.symbol,
                'side': o.side,
                'order_type': o.order_type,
                'limit_price': float(o.limit_price) if o.limit_price else None,
                'stop_price': float(o.stop_price) if o.stop_price else None,
                'qty': float(o.qty) if o.qty else None,
                'notional': float(o.notional) if o.notional else None,
                'filled_qty': float(o.filled_qty) if o.filled_qty else None,
                'filled_avg_price': float(o.filled_avg_price) if o.filled_avg_price else None,
                'status': o.status,
                'time_in_force': o.time_in_force,
                'submitted_at': o.submitted_at,
                'filled_at': o.filled_at,
                'expired_at': o.expired_at,
                'canceled_at': o.canceled_at,
                'failed_at': o.failed_at,
                'replaced_at': o.replaced_at,
                'replaced_by': o.replaced_by,
                'replaces': o.replaces,
                'asset_id': o.asset_id,
            }
            for o in orders
        ]
    
    def get_clock(self) -> Dict[str, Any]:
        """Get market clock"""
        clock = self.api.get_clock()
        return {
            'timestamp': clock.timestamp,
            'is_open': clock.is_open,
            'next_open': clock.next_open,
            'next_close': clock.next_close,
        }
    
    def get_calendar(
        self,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """Get market calendar"""
        calendar = self.api.get_calendar(start=start, end=end)
        return [
            {
                'date': c.date,
                'open': c.open,
                'close': c.close,
            }
            for c in calendar
        ]
