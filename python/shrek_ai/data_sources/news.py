"""
Comprehensive news aggregator.

Sources:
- Yahoo Finance news feed
- PR Newswire RSS by company
- Business Wire RSS by company
- Google News RSS by query
- SEC 8-K material event filings
- Benzinga (free tier)
- Finnhub (free tier)
"""

import re
import json
import time
from typing import Optional, Dict, Any, List
from pathlib import Path
from datetime import datetime, timedelta
from urllib.parse import quote
from loguru import logger
import requests
import feedparser
from bs4 import BeautifulSoup

from .content_extractor import ContentExtractor


class NewsAggregator:
    """Aggregate news from multiple sources for a company."""
    
    def __init__(self, cache_dir: Optional[Path] = None, storage_dir: Optional[Path] = None):
        self.cache_dir = cache_dir or Path('data/cache/news')
        self.storage_dir = storage_dir or Path('data/news')
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        
        self.extractor = ContentExtractor(cache_dir=self.cache_dir)
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            'Accept': 'application/rss+xml,application/xml,text/xml,*/*',
        }
        self.rate_limit_delay = 0.5
    
    def get_news(self, symbol: str, company_name: str = '', days: int = 30, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get comprehensive news for a symbol.
        
        Args:
            symbol: Stock symbol
            company_name: Full company name for better search
            days: How many days back to search
            limit: Maximum articles per source
        
        Returns:
            List of news articles
        """
        all_news = []
        
        # Yahoo Finance
        yahoo_news = self._fetch_yahoo_finance(symbol, limit)
        all_news.extend(yahoo_news)
        
        # PR Newswire
        pr_news = self._fetch_pr_newswire(symbol, company_name, limit)
        all_news.extend(pr_news)
        
        # Business Wire
        bw_news = self._fetch_business_wire(symbol, company_name, limit)
        all_news.extend(bw_news)
        
        # Google News RSS
        google_news = self._fetch_google_news(symbol, company_name, limit)
        all_news.extend(google_news)
        
        # SEC 8-K material events
        sec_news = self._fetch_sec_material_events(symbol, days)
        all_news.extend(sec_news)
        
        # Deduplicate by URL
        seen_urls = set()
        deduped = []
        for article in all_news:
            url = article.get('url', '')
            if url and url not in seen_urls:
                seen_urls.add(url)
                deduped.append(article)
            elif not url:
                deduped.append(article)
        
        # Sort by date descending
        deduped.sort(key=lambda x: x.get('published', ''), reverse=True)
        
        # Filter by date
        cutoff = datetime.now() - timedelta(days=days)
        recent = []
        for article in deduped:
            pub_date = article.get('published', '')
            if pub_date:
                try:
                    dt = datetime.strptime(pub_date[:10], '%Y-%m-%d')
                    if dt >= cutoff:
                        recent.append(article)
                except:
                    recent.append(article)  # Include if can't parse date
            else:
                recent.append(article)
        
        logger.info(f"Fetched {len(recent)} news articles for {symbol}")
        return recent[:limit]
    
    def _fetch_yahoo_finance(self, symbol: str, limit: int) -> List[Dict[str, Any]]:
        """Fetch news from Yahoo Finance."""
        articles = []
        
        try:
            url = f"https://finance.yahoo.com/quote/{symbol}/news"
            html = self.extractor.fetch_url(url, retries=2, delay=1.0)
            
            if not html:
                return articles
            
            soup = BeautifulSoup(html, 'html.parser')
            
            # Find news article links
            for link in soup.find_all('a', href=True):
                href = link.get('href', '')
                text = link.get_text(strip=True)
                
                # Yahoo Finance news articles
                if '/news/' in href and text and len(text) > 20:
                    if href.startswith('/'):
                        href = f"https://finance.yahoo.com{href}"
                    
                    # Try to get full article content
                    try:
                        time.sleep(self.rate_limit_delay)
                        article_html = self.extractor.fetch_url(href, retries=1, delay=0.5)
                        if article_html:
                            extracted = self.extractor.extract_from_html(article_html, href)
                            content = self.extractor.clean_text(extracted['content'])
                        else:
                            content = text
                    except:
                        content = text
                    
                    articles.append({
                        'symbol': symbol,
                        'source': 'yahoo_finance',
                        'url': href,
                        'title': text,
                        'content': content[:5000],
                        'published': datetime.now().strftime('%Y-%m-%d'),
                        'summary': text,
                    })
                    
                    if len(articles) >= limit:
                        break
        
        except Exception as e:
            logger.warning(f"Failed to fetch Yahoo Finance news for {symbol}: {e}")
        
        return articles
    
    def _fetch_pr_newswire(self, symbol: str, company_name: str, limit: int) -> List[Dict[str, Any]]:
        """Fetch news from PR Newswire RSS."""
        articles = []
        
        try:
            # PR Newswire search RSS
            query = quote(f"{symbol} {company_name}".strip())
            rss_url = f"https://www.prnewswire.com/rss/{query}-news.xml"
            
            feed = feedparser.parse(rss_url)
            
            for entry in feed.entries[:limit]:
                try:
                    # Try to get full article content
                    content = entry.get('summary', '')
                    if entry.get('link'):
                        time.sleep(self.rate_limit_delay)
                        article_html = self.extractor.fetch_url(entry.link, retries=1, delay=0.5)
                        if article_html:
                            extracted = self.extractor.extract_from_html(article_html, entry.link)
                            full_content = self.extractor.clean_text(extracted['content'])
                            if len(full_content) > len(content):
                                content = full_content
                except:
                    pass
                
                articles.append({
                    'symbol': symbol,
                    'source': 'pr_newswire',
                    'url': entry.get('link', ''),
                    'title': entry.get('title', ''),
                    'content': content[:5000],
                    'published': self._parse_date(entry.get('published', '')),
                    'summary': entry.get('summary', '')[:500],
                })
        
        except Exception as e:
            logger.warning(f"Failed to fetch PR Newswire for {symbol}: {e}")
        
        return articles
    
    def _fetch_business_wire(self, symbol: str, company_name: str, limit: int) -> List[Dict[str, Any]]:
        """Fetch news from Business Wire RSS."""
        articles = []
        
        try:
            query = quote(f"{symbol} {company_name}".strip())
            rss_url = f"https://www.businesswire.com/portal/site/home/newsindex/?javax.portlet.tpst=e33e97a9f84b9b5d0155c82a5e9d36af&vnsId=31333&javax.portlet.prp_e33e97a9f84b9b5d0155c82a5e9d36af=searchQuery%3D{query}"
            
            feed = feedparser.parse(rss_url)
            
            for entry in feed.entries[:limit]:
                articles.append({
                    'symbol': symbol,
                    'source': 'business_wire',
                    'url': entry.get('link', ''),
                    'title': entry.get('title', ''),
                    'content': entry.get('summary', '')[:5000],
                    'published': self._parse_date(entry.get('published', '')),
                    'summary': entry.get('summary', '')[:500],
                })
        
        except Exception as e:
            logger.warning(f"Failed to fetch Business Wire for {symbol}: {e}")
        
        return articles
    
    def _fetch_google_news(self, symbol: str, company_name: str, limit: int) -> List[Dict[str, Any]]:
        """Fetch news from Google News RSS."""
        articles = []
        
        try:
            query = quote(f"{symbol} stock {company_name}".strip())
            rss_url = f"https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"
            
            feed = feedparser.parse(rss_url)
            
            for entry in feed.entries[:limit]:
                content = entry.get('summary', '')
                
                # Try to get full article
                if entry.get('link'):
                    try:
                        time.sleep(self.rate_limit_delay)
                        # Google News links are redirects, follow them
                        response = requests.get(entry.link, headers=self.headers, timeout=10, allow_redirects=True)
                        final_url = response.url
                        
                        article_html = self.extractor.fetch_url(final_url, retries=1, delay=0.5)
                        if article_html:
                            extracted = self.extractor.extract_from_html(article_html, final_url)
                            full_content = self.extractor.clean_text(extracted['content'])
                            if len(full_content) > len(content):
                                content = full_content
                    except:
                        pass
                
                articles.append({
                    'symbol': symbol,
                    'source': 'google_news',
                    'url': entry.get('link', ''),
                    'title': entry.get('title', ''),
                    'content': content[:5000],
                    'published': self._parse_date(entry.get('published', '')),
                    'summary': entry.get('summary', '')[:500],
                })
        
        except Exception as e:
            logger.warning(f"Failed to fetch Google News for {symbol}: {e}")
        
        return articles
    
    def _fetch_sec_material_events(self, symbol: str, days: int) -> List[Dict[str, Any]]:
        """Fetch material events from SEC 8-K filings."""
        articles = []
        
        try:
            from ..sec_edgar import SECEdgar
            
            edgar = SECEdgar()
            filings = edgar.get_filings(symbol, filing_type='8-K', count=20)
            
            cutoff = datetime.now() - timedelta(days=days)
            
            for filing in filings:
                try:
                    filing_date = datetime.strptime(filing['filing_date'], '%Y-%m-%d')
                    if filing_date < cutoff:
                        continue
                    
                    content = edgar.get_filing_content(filing['filing_url'])
                    if not content:
                        continue
                    
                    # Check for material event items
                    soup = BeautifulSoup(content, 'html.parser')
                    text = soup.get_text(separator='\n', strip=True)
                    text_lower = text.lower()
                    
                    # Look for material event indicators
                    material_items = []
                    item_patterns = [
                        r'Item\s+1\.01\s*[-:]\s*Entry\s+into\s+a\s+Material\s+Definitive\s+Agreement',
                        r'Item\s+1\.02\s*[-:]\s*Termination\s+of\s+a\s+Material\s+Definitive\s+Agreement',
                        r'Item\s+1\.03\s*[-:]\s*Bankruptcy\s+or\s+Receivership',
                        r'Item\s+1\.04\s*[-:]\s+Mine\s+Safety',
                        r'Item\s+2\.01\s*[-:]\s*Completion\s+of\s+Acquisition\s+or\s+Disposition',
                        r'Item\s+2\.02\s*[-:]\s*Results\s+of\s+Operations',
                        r'Item\s+2\.03\s*[-:]\s*Creation\s+of\s+a\s+Direct\s+Financial\s+Obligation',
                        r'Item\s+2\.04\s*[-:]\s*Triggering\s+Events\s+That\s+Accelerate',
                        r'Item\s+2\.05\s*[-:]\s*Cost\s+Associated\s+with\s+Exit\s+or\s+Disposal',
                        r'Item\s+2\.06\s*[-:]\s*Material\s+Impairments',
                        r'Item\s+3\.01\s*[-:]\s*Notice\s+of\s+Delisting',
                        r'Item\s+3\.02\s*[-:]\s*Unregistered\s+Sales\s+of\s+Equity\s+Securities',
                        r'Item\s+3\.03\s*[-:]\s*Material\s+Modification\s+to\s+Rights\s+of\s+Security\s+Holders',
                        r'Item\s+4\.01\s*[-:]\s*Changes\s+in\s+Registrant\'s\s+Certifying\s+Accountant',
                        r'Item\s+4\.02\s*[-:]\s*Non-Reliance\s+on\s+Previously\s+Issued\s+Financial\s+Statements',
                        r'Item\s+5\.01\s*[-:]\s*Changes\s+in\s+Control\s+of\s+Registrant',
                        r'Item\s+5\.02\s*[-:]\s*Departure\s+of\s+Directors\s+or\s+Principal\s+Officers',
                        r'Item\s+5\.03\s*[-:]\s*Amendments\s+to\s+Articles\s+of\s+Incorporation',
                        r'Item\s+5\.04\s*[-:]\s*Temporary\s+Suspension\s+of\s+Trading',
                        r'Item\s+5\.05\s*[-:]\s*Amendment\s+to\s+Registrant\'s\s+Code\s+of\s+Ethics',
                        r'Item\s+5\.06\s*[-:]\s*Change\s+in\s+Shell\s+Company\s+Status',
                        r'Item\s+5\.07\s*[-:]\s*Submission\s+of\s+Matters\s+to\s+a\s+Vote\s+of\s+Security\s+Holders',
                        r'Item\s+5\.08\s*[-:]\s*Shareholder\s+Director\s+Nominations',
                        r'Item\s+6\.01\s*[-:]\s*ABS\s+Informational\s+and\s+Computational\s+Materials',
                        r'Item\s+6\.02\s*[-:]\s*Change\s+of\s+Servicer\s+or\s+Trustee',
                        r'Item\s+6\.03\s*[-:]\s*Change\s+in\s+Credit\s+Enhancement',
                        r'Item\s+6\.04\s*[-:]\s*Failure\s+of\s+a\s+Registered\s+Principal',
                        r'Item\s+6\.05\s*[-:]\s*Change\s+in\s+Class\s+of\s+Securities',
                        r'Item\s+7\.01\s*[-:]\s*Regulation\s+FD\s+Disclosure',
                        r'Item\s+8\.01\s*[-:]\s*Other\s+Events',
                        r'Item\s+9\.01\s*[-:]\s*Financial\s+Statements\s+and\s+Exhibits',
                    ]
                    
                    for pattern in item_patterns:
                        if re.search(pattern, text, re.IGNORECASE):
                            item_name = pattern.split('[-:]')[1].strip() if '[-:]' in pattern else 'Material Event'
                            material_items.append(item_name)
                    
                    if material_items:
                        articles.append({
                            'symbol': symbol,
                            'source': 'sec_8k',
                            'url': filing['filing_url'],
                            'title': f"8-K Filing: {', '.join(material_items[:3])}",
                            'content': text[:8000],
                            'published': filing['filing_date'],
                            'summary': f"SEC 8-K filing covering: {', '.join(material_items[:3])}",
                            'material_items': material_items,
                        })
                
                except Exception as e:
                    logger.warning(f"Failed to process 8-K for {symbol}: {e}")
                    continue
        
        except Exception as e:
            logger.warning(f"Failed to fetch SEC material events for {symbol}: {e}")
        
        return articles
    
    def _parse_date(self, date_str: str) -> str:
        """Parse various date formats."""
        if not date_str:
            return datetime.now().strftime('%Y-%m-%d')
        
        formats = [
            '%Y-%m-%dT%H:%M:%SZ',
            '%Y-%m-%dT%H:%M:%S%z',
            '%Y-%m-%d %H:%M:%S',
            '%a, %d %b %Y %H:%M:%S %z',
            '%Y-%m-%d',
        ]
        
        for fmt in formats:
            try:
                dt = datetime.strptime(date_str, fmt)
                return dt.strftime('%Y-%m-%d')
            except:
                continue
        
        return datetime.now().strftime('%Y-%m-%d')
    
    def filter_thesis_relevant(self, articles: List[Dict[str, Any]], keywords: List[str]) -> List[Dict[str, Any]]:
        """Filter articles relevant to investment thesis."""
        if not keywords:
            return articles
        
        relevant = []
        for article in articles:
            text = f"{article.get('title', '')} {article.get('summary', '')} {article.get('content', '')}".lower()
            
            for keyword in keywords:
                if keyword.lower() in text:
                    relevant.append(article)
                    break
        
        return relevant
    
    def extract_events(self, articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Extract thesis-relevant events from news."""
        events = []
        
        # Keywords that signal material events
        event_keywords = [
            'partnership', 'collaboration', 'joint venture', 'strategic alliance',
            'contract award', 'government contract', 'defense contract',
            'FDA approval', 'regulatory approval', 'clinical trial',
            'acquisition', 'merger', 'divestiture', 'spin-off',
            'patent', 'intellectual property', 'licensing',
            'product launch', 'new product', 'platform',
            'guidance', 'outlook', 'forecast',
            'sec investigation', 'lawsuit', 'settlement',
            'CEO departure', 'management change', 'board change',
            'cybersecurity', 'data breach', 'security incident',
        ]
        
        for article in articles:
            text = f"{article.get('title', '')} {article.get('summary', '')}".lower()
            
            for keyword in event_keywords:
                if keyword in text:
                    events.append({
                        'date': article.get('published', ''),
                        'source': article.get('source', ''),
                        'event_type': keyword,
                        'title': article.get('title', ''),
                        'url': article.get('url', ''),
                        'summary': article.get('summary', ''),
                    })
                    break
        
        return events
