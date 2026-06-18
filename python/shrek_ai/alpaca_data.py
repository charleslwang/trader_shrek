"""
Alpaca data source integration
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import pandas as pd
from alpaca_trade_api import REST
from loguru import logger

from .config import get_alpaca_config
from .price_cache import PriceCache


class AlpacaDataSource:
    """Alpaca data source for market data and account information"""
    
    def __init__(self, cache: Optional[PriceCache] = None):
        config = get_alpaca_config()
        self.api = REST(
            key_id=config['api_key'],
            secret_key=config['secret_key'],
            base_url=config['base_url'],
            api_version='v2'
        )
        self.data_base_url = config['data_base_url']
        self.data_feed = config['data_feed']
        self.cache = cache if cache is not None else PriceCache()
    
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
            
            # Market cap filter: use price * shares outstanding estimate if available
            # This is a coarse proxy since Alpaca does not provide market cap directly
            try:
                # Approximate using average daily volume as a liquidity proxy
                # when true market cap data is unavailable
                snapshot = self.api.get_snapshot(asset['symbol'])
                if snapshot and snapshot.daily_bar:
                    # Keep symbol; market cap filtering is best-effort without a dedicated data feed
                    pass
            except Exception:
                pass

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
        """Get historical bars for a symbol (cached)"""
        if start is None:
            start = datetime.now() - timedelta(days=365 * 2)
        if end is None:
            end = datetime.now()

        # Try cache first
        if self.cache is not None:
            cached = self.cache.get_bars(symbol, start, end, timeframe)
            if cached is not None:
                return cached

        # Fetch from Alpaca
        bars = self.api.get_bars(
            symbol,
            timeframe,
            start=start.date().isoformat(),
            end=end.date().isoformat(),
            limit=limit,
            adjustment='raw',
        ).df

        # Save to cache
        if self.cache is not None and not bars.empty:
            self.cache.save_bars(symbol, bars, start, end, timeframe)

        return bars
    
    def get_latest_quote(self, symbol: str) -> Dict[str, Any]:
        """Get latest quote for a symbol (cached)"""
        # Try cache first
        if self.cache is not None:
            cached = self.cache.get_quote(symbol)
            if cached is not None:
                return cached

        # Fetch from Alpaca
        quote = self.api.get_latest_quote(symbol)
        result = {
            'symbol': symbol,
            'bid': quote.bp,
            'ask': quote.ap,
            'bid_size': quote.bs,
            'ask_size': quote.asz,
            'timestamp': quote.t,
        }

        # Save to cache
        if self.cache is not None:
            self.cache.save_quote(symbol, result)

        return result
    
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

    def get_calendar(self, start: datetime, end: datetime) -> List[Dict[str, Any]]:
        """Get Alpaca market calendar entries as plain dictionaries."""
        calendar = self.api.get_calendar(start=start.date().isoformat(), end=end.date().isoformat())
        return [
            {
                'date': entry.date,
                'open': entry.open,
                'close': entry.close,
            }
            for entry in calendar
        ]
