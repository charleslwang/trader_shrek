"""
Research report aggregator.

Sources:
- Seeking Alpha research articles (free)
- Zacks Investment Research (free summaries)
- TipRanks analyst consensus
- Simply Wall St (free summaries)
- Finviz analyst recommendations
- MarketWatch analysis
- Benzinga Pro research (free tier)
"""

import re
import json
import time
from typing import Optional, Dict, Any, List
from pathlib import Path
from urllib.parse import quote
from loguru import logger
import requests
from bs4 import BeautifulSoup

from .content_extractor import ContentExtractor


class ResearchReportAggregator:
    """Aggregate research reports and analyst opinions."""
    
    def __init__(self, cache_dir: Optional[Path] = None, storage_dir: Optional[Path] = None):
        self.cache_dir = cache_dir or Path('data/cache/research')
        self.storage_dir = storage_dir or Path('data/research')
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        
        self.extractor = ContentExtractor(cache_dir=self.cache_dir)
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        }
        self.rate_limit_delay = 0.5
    
    def get_research(self, symbol: str, company_name: str = '') -> Dict[str, Any]:
        """
        Get comprehensive research for a symbol.
        
        Args:
            symbol: Stock symbol
            company_name: Full company name
        
        Returns:
            Dictionary with analyst opinions, ratings, and research summaries
        """
        results = {
            'symbol': symbol,
            'analyst_consensus': {},
            'price_targets': {},
            'research_articles': [],
            'bullish_theses': [],
            'bearish_theses': [],
            'consolidated_text': '',
        }
        
        # Seeking Alpha research
        sa_research = self._fetch_seeking_alpha_research(symbol)
        results['research_articles'].extend(sa_research)
        
        # TipRanks analyst consensus
        tipranks = self._fetch_tipranks(symbol)
        results['analyst_consensus'] = tipranks
        
        # Finviz analyst recommendations
        finviz = self._fetch_finviz(symbol)
        if finviz:
            results['price_targets'] = finviz.get('price_targets', {})
        
        # Zacks rank
        zacks = self._fetch_zacks(symbol)
        if zacks:
            results['zacks_rank'] = zacks
        
        # Extract bullish/bearish theses
        for article in results['research_articles']:
            text = f"{article.get('title', '')} {article.get('summary', '')}".lower()
            
            if any(kw in text for kw in ['buy', 'bullish', 'strong buy', 'outperform', 'overweight', 'upgrade']):
                results['bullish_theses'].append({
                    'source': article.get('source', ''),
                    'title': article.get('title', ''),
                    'summary': article.get('summary', ''),
                    'url': article.get('url', ''),
                })
            elif any(kw in text for kw in ['sell', 'bearish', 'underperform', 'underweight', 'downgrade', 'avoid']):
                results['bearish_theses'].append({
                    'source': article.get('source', ''),
                    'title': article.get('title', ''),
                    'summary': article.get('summary', ''),
                    'url': article.get('url', ''),
                })
        
        # Build consolidated text
        texts = []
        for article in results['research_articles']:
            texts.append(f"[{article.get('source', '')}] {article.get('title', '')}\n{article.get('summary', '')}")
        results['consolidated_text'] = '\n\n'.join(texts)
        
        logger.info(f"Aggregated {len(results['research_articles'])} research items for {symbol}")
        return results
    
    def _fetch_seeking_alpha_research(self, symbol: str) -> List[Dict[str, Any]]:
        """Fetch research articles from Seeking Alpha."""
        articles = []
        
        try:
            # Seeking Alpha analysis page
            url = f"https://seekingalpha.com/symbol/{symbol}/analysis"
            html = self.extractor.fetch_url(url, retries=2, delay=2.0)
            
            if not html:
                return articles
            
            soup = BeautifulSoup(html, 'html.parser')
            
            for article in soup.find_all('a', href=True):
                href = article.get('href', '')
                text = article.get_text(strip=True)
                
                if '/article/' in href and text and len(text) > 20:
                    if href.startswith('/'):
                        href = f"https://seekingalpha.com{href}"
                    
                    # Determine sentiment
                    sentiment = 'neutral'
                    text_lower = text.lower()
                    if any(kw in text_lower for kw in ['buy', 'bullish', 'strong', 'outperform']):
                        sentiment = 'bullish'
                    elif any(kw in text_lower for kw in ['sell', 'bearish', 'avoid', 'underperform']):
                        sentiment = 'bearish'
                    
                    # Try to get summary
                    summary = ''
                    try:
                        time.sleep(self.rate_limit_delay)
                        article_html = self.extractor.fetch_url(href, retries=1, delay=1.0)
                        if article_html:
                            extracted = self.extractor.extract_from_html(article_html, href)
                            summary = self.extractor.clean_text(extracted['content'])[:3000]
                    except:
                        pass
                    
                    articles.append({
                        'symbol': symbol,
                        'source': 'seeking_alpha',
                        'url': href,
                        'title': text,
                        'summary': summary,
                        'sentiment': sentiment,
                        'published': time.strftime('%Y-%m-%d'),
                    })
                    
                    if len(articles) >= 10:
                        break
        
        except Exception as e:
            logger.warning(f"Failed to fetch Seeking Alpha research for {symbol}: {e}")
        
        return articles
    
    def _fetch_tipranks(self, symbol: str) -> Dict[str, Any]:
        """Fetch analyst consensus from TipRanks."""
        consensus = {}
        
        try:
            url = f"https://www.tipranks.com/stocks/{symbol.lower()}"
            html = self.extractor.fetch_url(url, retries=2, delay=2.0)
            
            if not html:
                return consensus
            
            soup = BeautifulSoup(html, 'html.parser')
            
            # Look for analyst ratings
            # TipRanks structure changes, so we use broad selectors
            rating_text = soup.get_text()
            
            # Extract rating distribution
            buy_match = re.search(r'(\d+)\s*Buy', rating_text)
            hold_match = re.search(r'(\d+)\s*Hold', rating_text)
            sell_match = re.search(r'(\d+)\s*Sell', rating_text)
            
            if buy_match or hold_match or sell_match:
                consensus['buy_count'] = int(buy_match.group(1)) if buy_match else 0
                consensus['hold_count'] = int(hold_match.group(1)) if hold_match else 0
                consensus['sell_count'] = int(sell_match.group(1)) if sell_match else 0
                total = consensus['buy_count'] + consensus['hold_count'] + consensus['sell_count']
                if total > 0:
                    consensus['buy_pct'] = consensus['buy_count'] / total
                    consensus['hold_pct'] = consensus['hold_count'] / total
                    consensus['sell_pct'] = consensus['sell_count'] / total
            
            # Extract price target
            pt_match = re.search(r'\$?([\d,.]+)\s*(?:price target|target price)', rating_text, re.IGNORECASE)
            if pt_match:
                consensus['price_target'] = float(pt_match.group(1).replace(',', ''))
        
        except Exception as e:
            logger.warning(f"Failed to fetch TipRanks for {symbol}: {e}")
        
        return consensus
    
    def _fetch_finviz(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Fetch analyst data from Finviz."""
        try:
            url = f"https://finviz.com/quote.ashx?t={symbol}"
            html = self.extractor.fetch_url(url, retries=2, delay=1.0)
            
            if not html:
                return None
            
            soup = BeautifulSoup(html, 'html.parser')
            text = soup.get_text()
            
            result = {}
            
            # Target price
            target_match = re.search(r'Target\s+Price\s+\$?([\d,.]+)', text)
            if target_match:
                result['price_targets'] = {'target': float(target_match.group(1).replace(',', ''))}
            
            # Analyst recommendation
            rec_match = re.search(r'Recom\s+([\d.]+)', text)
            if rec_match:
                result['recommendation_score'] = float(rec_match.group(1))
            
            return result
        
        except Exception as e:
            logger.warning(f"Failed to fetch Finviz for {symbol}: {e}")
            return None
    
    def _fetch_zacks(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Fetch Zacks rank."""
        try:
            url = f"https://www.zacks.com/stock/quote/{symbol}"
            html = self.extractor.fetch_url(url, retries=2, delay=1.0)
            
            if not html:
                return None
            
            soup = BeautifulSoup(html, 'html.parser')
            text = soup.get_text()
            
            # Zacks rank
            rank_match = re.search(r'Zacks Rank\s*[:\-]?\s*(\d)\s*[-–]\s*(Strong Buy|Buy|Hold|Sell|Strong Sell)', text, re.IGNORECASE)
            if rank_match:
                return {
                    'rank': int(rank_match.group(1)),
                    'rank_text': rank_match.group(2),
                }
            
            return None
        
        except Exception as e:
            logger.warning(f"Failed to fetch Zacks for {symbol}: {e}")
            return None
    
    def load_saved_research(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Load previously saved research."""
        filepath = self.storage_dir / f"{symbol}_research.json"
        if not filepath.exists():
            return None
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load research for {symbol}: {e}")
            return None
    
    def save_research(self, symbol: str, research: Dict[str, Any]) -> Path:
        """Save research to storage."""
        filepath = self.storage_dir / f"{symbol}_research.json"
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(research, f, indent=2, ensure_ascii=False)
        
        return filepath
