"""
Discovery engine for finding new candidates outside the base list

Scans high-activity sources for stocks showing momentum, earnings surprises,
or sector rotation signals that might warrant research attention.
"""

import re
from typing import List, Set, Dict, Any
from pathlib import Path
from datetime import datetime, timedelta
from loguru import logger
import requests
import feedparser

from .alpaca_data import AlpacaDataSource


class CandidateDiscovery:
    """Discovers new trading candidates from market activity signals"""
    
    def __init__(self, base_candidates_path: Path = Path('data/candidates.txt')):
        self.base_candidates_path = base_candidates_path
        self.alpaca = AlpacaDataSource()
        
    def load_base_candidates(self) -> Set[str]:
        """Load existing candidate symbols"""
        if not self.base_candidates_path.exists():
            return set()
        with open(self.base_candidates_path, 'r') as f:
            return {line.strip().upper() for line in f if line.strip() and not line.strip().startswith('#')}
    
    def discover_from_yahoo_most_active(self, max_results: int = 25) -> List[Dict[str, Any]]:
        """Fetch most active stocks from Yahoo Finance"""
        discovered = []
        try:
            url = "https://query1.finance.yahoo.com/v1/finance/search"
            params = {"q": "", "quotesCount": max_results, "newsCount": 0, "listsCount": 1}
            response = requests.get(url, params=params, timeout=15)
            data = response.json()
            
            for item in data.get('quotes', []):
                symbol = item.get('symbol', '').upper()
                if not symbol or not symbol.isalpha() or len(symbol) > 5:
                    continue
                # Skip OTC, foreign, crypto
                if any(c.isdigit() for c in symbol):
                    continue
                discovered.append({
                    'symbol': symbol,
                    'name': item.get('shortname', item.get('longname', '')),
                    'source': 'yahoo_active',
                    'score': 0.5,
                })
        except Exception as e:
            logger.warning(f"Yahoo discovery failed: {e}")
        
        return discovered
    
    def discover_from_earnings_calendar(self, days_ahead: int = 7) -> List[Dict[str, Any]]:
        """Discover stocks with upcoming earnings"""
        discovered = []
        try:
            # Use Yahoo Finance earnings calendar API
            today = datetime.now()
            for day_offset in range(days_ahead):
                date = today + timedelta(days=day_offset)
                date_str = date.strftime('%Y-%m-%d')
                
                url = f"https://finance.yahoo.com/calendar/earnings?day={date_str}"
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
                }
                response = requests.get(url, headers=headers, timeout=10)
                
                # Extract symbols from HTML
                symbols = re.findall(r'"symbol":"([A-Z]{1,5})"', response.text)
                for sym in set(symbols):
                    discovered.append({
                        'symbol': sym,
                        'name': '',
                        'source': 'earnings_calendar',
                        'score': 0.6,
                    })
        except Exception as e:
            logger.warning(f"Earnings calendar discovery failed: {e}")
        
        return discovered
    
    def discover_from_news_feeds(self, max_per_feed: int = 10) -> List[Dict[str, Any]]:
        """Discover symbols mentioned in financial news feeds"""
        discovered = []
        
        feeds = [
            'https://www.marketwatch.com/rss/topstories',
            'https://feeds.finance.yahoo.com/rss/2.0/headlines?s=^gspc&region=US&lang=en-US',
        ]
        
        symbol_pattern = re.compile(r'\b([A-Z]{1,5})\b')
        
        for feed_url in feeds:
            try:
                parsed = feedparser.parse(feed_url)
                for entry in parsed.entries[:max_per_feed]:
                    text = f"{entry.get('title', '')} {entry.get('summary', '')}"
                    symbols = symbol_pattern.findall(text)
                    for sym in symbols:
                        if sym.isalpha() and len(sym) >= 2:
                            discovered.append({
                                'symbol': sym,
                                'name': '',
                                'source': 'news_feed',
                                'score': 0.4,
                            })
            except Exception as e:
                logger.debug(f"Feed parse failed for {feed_url}: {e}")
        
        return discovered
    
    def screen_discovered(self, candidates: List[Dict[str, Any]], base_symbols: Set[str]) -> List[Dict[str, Any]]:
        """
        Screen discovered candidates for liquidity and price filters.
        Returns candidates that pass basic filters and are NOT already in base list.
        """
        new_candidates = []
        
        for cand in candidates:
            symbol = cand['symbol']
            if symbol in base_symbols:
                continue
            
            try:
                # Check price and volume via Alpaca
                quote = self.alpaca.get_latest_quote(symbol)
                price = (quote['bid'] + quote['ask']) / 2
                
                # Basic filters
                if price < 2.0 or price > 1000.0:
                    continue
                
                # Get volume
                bars = self.alpaca.get_bars(symbol, timeframe='day', limit=5)
                if len(bars) > 0:
                    avg_volume = bars['volume'].mean()
                    if avg_volume < 1_000_000:  # Skip illiquid
                        continue
                    
                    cand['price'] = price
                    cand['avg_volume'] = int(avg_volume)
                    cand['screen_passed'] = True
                    new_candidates.append(cand)
                    
            except Exception as e:
                logger.debug(f"Screen failed for {symbol}: {e}")
                continue
        
        # Deduplicate and sort by score
        seen = set()
        deduped = []
        for c in sorted(new_candidates, key=lambda x: x.get('score', 0), reverse=True):
            if c['symbol'] not in seen:
                seen.add(c['symbol'])
                deduped.append(c)
        
        return deduped
    
    def run_discovery(self, max_new_candidates: int = 10) -> List[Dict[str, Any]]:
        """
        Full discovery pipeline. Returns new candidates that passed screening.
        """
        logger.info("=== Running Candidate Discovery ===")
        
        base_symbols = self.load_base_candidates()
        logger.info(f"Base candidate list has {len(base_symbols)} symbols")
        
        all_discovered = []
        
        # Source 1: Yahoo most active
        yahoo = self.discover_from_yahoo_most_active(max_results=30)
        logger.info(f"Discovered {len(yahoo)} from Yahoo active")
        all_discovered.extend(yahoo)
        
        # Source 2: Earnings calendar
        earnings = self.discover_from_earnings_calendar(days_ahead=5)
        logger.info(f"Discovered {len(earnings)} from earnings calendar")
        all_discovered.extend(earnings)
        
        # Source 3: News feeds
        news = self.discover_from_news_feeds(max_per_feed=10)
        logger.info(f"Discovered {len(news)} from news feeds")
        all_discovered.extend(news)
        
        # Screen
        screened = self.screen_discovered(all_discovered, base_symbols)
        logger.info(f"Screened down to {len(screened)} new candidates")
        
        # Return top N
        top = screened[:max_new_candidates]
        
        for c in top:
            logger.info(
                f"New candidate: {c['symbol']} "
                f"(price=${c.get('price', 0):.2f}, "
                f"vol={c.get('avg_volume', 0):,}, "
                f"source={c['source']})"
            )
        
        return top
    
    def add_to_candidates(self, symbols: List[str], reason: str = "discovered"):
        """Append discovered symbols to candidates.txt"""
        if not symbols:
            return
        
        existing = self.load_base_candidates()
        new = [s.upper() for s in symbols if s.upper() not in existing]
        
        if not new:
            logger.info("No new symbols to add")
            return
        
        with open(self.base_candidates_path, 'a') as f:
            f.write(f"\n# Discovered {datetime.now().date().isoformat()} - {reason}\n")
            for sym in new:
                f.write(f"{sym}\n")
        
        logger.info(f"Added {len(new)} symbols to candidates.txt: {new}")
        return new
