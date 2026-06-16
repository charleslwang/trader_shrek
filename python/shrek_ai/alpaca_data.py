"""
Alpaca data source integration
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import pandas as pd
from alpaca_trade_api import REST
from loguru import logger

from .config import get_alpaca_config


class AlpacaDataSource:
    """Alpaca data source for market data and account information"""
    
    def __init__(self):
        config = get_alpaca_config()
        self.api = REST(
            key_id=config['api_key'],
            secret_key=config['secret_key'],
            base_url=config['base_url'],
            api_version='v2'
        )
        self.data_base_url = config['data_base_url']
        self.data_feed = config['data_feed']
    
    def get_assets(self) -> List[Dict[str, Any]]:
        """Get all tradable assets"""
        assets = self.api.list_assets(status='active')
        return [
            {
                'symbol': a.symbol,
                'name': a.name,
                'exchange': a.exchange,
                'asset_class': a.class_name,
                'tradable': a.tradable,
                'fractionable': a.fractionable,
                'marginable': a.marginable,
                'shortable': a.shortable,
            }
            for a in assets
        ]
    
    def build_universe(
        self,
        min_price: float = 2.0,
        max_price: float = 1000.0,
        min_market_cap: int = 100_000_000,
        require_fractionable: bool = True,
        require_tradable: bool = True,
        asset_class: str = 'us_equity',
    ) -> List[str]:
        """Build universe of symbols based on filters"""
        assets = self.get_assets()
        
        universe = []
        for asset in assets:
            # Filter by asset class
            if asset['asset_class'] != asset_class:
                continue
            
            # Filter by tradability
            if require_tradable and not asset['tradable']:
                continue
            
            # Filter by fractionable
            if require_fractionable and not asset['fractionable']:
                continue
            
            # Get current price for price filter
            try:
                quote = self.api.get_latest_quote(asset['symbol'])
                price = quote.ap if quote.ap else quote.bp
                if price is None:
                    continue
                
                if price < min_price or price > max_price:
                    continue
            except Exception as e:
                logger.warning(f"Failed to get quote for {asset['symbol']}: {e}")
                continue
            
            # Market cap filter would require additional data source
            # For now, we'll skip this filter
            
            universe.append(asset['symbol'])
        
        logger.info(f"Built universe with {len(universe)} symbols")
        return universe
    
    def get_bars(
        self,
        symbol: str,
        timeframe: str = 'day',
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        limit: int = 1000,
    ) -> pd.DataFrame:
        """Get historical bars for a symbol"""
        if start is None:
            start = datetime.now() - timedelta(days=365 * 2)
        if end is None:
            end = datetime.now()
        
        bars = self.api.get_bars(
            symbol,
            timeframe,
            start=start,
            end=end,
            limit=limit,
            adjustment='raw',
        ).df
        
        return bars
    
    def get_latest_quote(self, symbol: str) -> Dict[str, Any]:
        """Get latest quote for a symbol"""
        quote = self.api.get_latest_quote(symbol)
        return {
            'symbol': symbol,
            'bid': quote.bp,
            'ask': quote.ap,
            'bid_size': quote.bs,
            'ask_size': quote.asz,
            'timestamp': quote.t,
        }
    
    def get_snapshot(self, symbol: str) -> Dict[str, Any]:
        """Get snapshot for a symbol"""
        snapshot = self.api.get_snapshot(symbol)
        return {
            'symbol': symbol,
            'latest_trade': snapshot.latest_trade,
            'latest_quote': snapshot.latest_quote,
            'minute_bar': snapshot.minute_bar,
            'daily_bar': snapshot.daily_bar,
            'prev_daily_bar': snapshot.prev_daily_bar,
        }
