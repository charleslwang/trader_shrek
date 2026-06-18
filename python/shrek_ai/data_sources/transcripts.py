"""
Comprehensive earnings transcript fetcher.

Sources:
- Seeking Alpha (primary, free transcripts)
- Yahoo Finance earnings calendar
- Motley Fool
- Manual transcript uploads
- SEC EDGAR 8-K (earnings releases)
"""

import re
import json
import time
from typing import Optional, Dict, Any, List
from pathlib import Path
from datetime import datetime, timedelta
from loguru import logger
import requests
from bs4 import BeautifulSoup
import feedparser

from .content_extractor import ContentExtractor


class TranscriptFetcher:
    """Fetch earnings call transcripts from multiple sources."""
    
    def __init__(self, cache_dir: Optional[Path] = None, storage_dir: Optional[Path] = None):
        self.cache_dir = cache_dir or Path('data/cache/transcripts')
        self.storage_dir = storage_dir or Path('data/transcripts')
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        
        self.extractor = ContentExtractor(cache_dir=self.cache_dir)
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        }
        self.rate_limit_delay = 1.0
    
    def get_transcripts(self, symbol: str, quarters: int = 4) -> List[Dict[str, Any]]:
        """
        Get earnings transcripts for a symbol from all sources.
        
        Args:
            symbol: Stock symbol
            quarters: Number of quarters to fetch
        
        Returns:
            List of transcript data
        """
        transcripts = []
        
        # Try Seeking Alpha
        sa_transcripts = self._fetch_seeking_alpha(symbol, quarters)
        transcripts.extend(sa_transcripts)
        
        # Try Yahoo Finance
        yf_transcripts = self._fetch_yahoo_finance(symbol, quarters)
        # Merge, deduplicate by date
        existing_dates = {t['date'] for t in transcripts}
        for yt in yf_transcripts:
            if yt['date'] not in existing_dates:
                transcripts.append(yt)
        
        # Try SEC 8-K for earnings releases
        sec_releases = self._fetch_sec_earnings_releases(symbol, quarters)
        existing_dates = {t['date'] for t in transcripts}
        for sr in sec_releases:
            if sr['date'] not in existing_dates:
                transcripts.append(sr)
        
        # Sort by date descending
        transcripts.sort(key=lambda x: x.get('date', ''), reverse=True)
        
        logger.info(f"Fetched {len(transcripts)} transcripts for {symbol}")
        return transcripts[:quarters]
    
    def _fetch_seeking_alpha(self, symbol: str, quarters: int) -> List[Dict[str, Any]]:
        """Fetch transcripts from Seeking Alpha."""
        transcripts = []
        
        try:
            # Seeking Alpha symbol page
            url = f"https://seekingalpha.com/symbol/{symbol}/earnings/transcripts"
            html = self.extractor.fetch_url(url, retries=2, delay=2.0)
            
            if not html:
                return transcripts
            
            soup = BeautifulSoup(html, 'html.parser')
            
            # Find transcript links
            transcript_links = []
            for link in soup.find_all('a', href=True):
                href = link.get('href', '')
                text = link.get_text(strip=True)
                
                # Match earnings transcript links
                if 'earnings-call-transcript' in href.lower() or 'transcript' in href.lower():
                    if href.startswith('/'):
                        href = f"https://seekingalpha.com{href}"
                    transcript_links.append({
                        'url': href,
                        'title': text,
                    })
            
            # Fetch each transcript
            for link_info in transcript_links[:quarters * 2]:  # Fetch extra for dedup
                try:
                    time.sleep(self.rate_limit_delay)
                    transcript_html = self.extractor.fetch_url(link_info['url'], retries=2, delay=2.0)
                    
                    if not transcript_html:
                        continue
                    
                    soup = BeautifulSoup(transcript_html, 'html.parser')
                    
                    # Extract date
                    date = self._extract_date_from_title(link_info['title'])
                    if not date:
                        date = self._extract_date_from_html(transcript_html)
                    
                    # Extract content
                    content_div = soup.find('div', {'data-test-id': 'transcript-content'})
                    if not content_div:
                        content_div = soup.find('article') or soup.find('div', class_=re.compile('content|article'))
                    
                    if content_div:
                        content = content_div.get_text(separator='\n', strip=True)
                        
                        # Extract Q&A section
                        qa_section = self._extract_qa(content)
                        
                        transcripts.append({
                            'symbol': symbol,
                            'source': 'seeking_alpha',
                            'url': link_info['url'],
                            'title': link_info['title'],
                            'date': date,
                            'content': content,
                            'qa_section': qa_section,
                            'quarter': self._infer_quarter(date),
                        })
                        
                        self._save_transcript(transcripts[-1])
                        
                except Exception as e:
                    logger.warning(f"Failed to fetch Seeking Alpha transcript {link_info['url']}: {e}")
                    continue
        
        except Exception as e:
            logger.warning(f"Failed to fetch Seeking Alpha transcripts for {symbol}: {e}")
        
        return transcripts
    
    def _fetch_yahoo_finance(self, symbol: str, quarters: int) -> List[Dict[str, Any]]:
        """Fetch earnings data from Yahoo Finance."""
        transcripts = []
        
        try:
            # Yahoo Finance earnings history
            url = f"https://finance.yahoo.com/quote/{symbol}/analysis"
            html = self.extractor.fetch_url(url, retries=2, delay=1.0)
            
            if not html:
                return transcripts
            
            # Also try the earnings calendar
            calendar_url = f"https://finance.yahoo.com/calendar/earnings?symbol={symbol}"
            calendar_html = self.extractor.fetch_url(calendar_url, retries=2, delay=1.0)
            
            # Extract earnings surprise and EPS estimate data from Yahoo Finance tables
            
            soup = BeautifulSoup(html, 'html.parser') if html else None
            
            # Try to extract earnings history table
            if soup:
                tables = self.extractor.extract_tables_from_html(html)
                for table in tables:
                    # Look for earnings history
                    headers = [h.lower() for h in table.get('headers', [])]
                    if any('eps' in h or 'earnings' in h or 'surprise' in h for h in headers):
                        # This might be earnings data
                        logger.debug(f"Found potential earnings table for {symbol}")
        
        except Exception as e:
            logger.warning(f"Failed to fetch Yahoo Finance data for {symbol}: {e}")
        
        return transcripts
    
    def _fetch_sec_earnings_releases(self, symbol: str, quarters: int) -> List[Dict[str, Any]]:
        """Fetch earnings releases from SEC 8-K filings."""
        transcripts = []
        
        try:
            from ..sec_edgar import SECEdgar
            
            edgar = SECEdgar()
            filings = edgar.get_filings(symbol, filing_type='8-K', count=quarters * 3)
            
            for filing in filings:
                try:
                    content = edgar.get_filing_content(filing['filing_url'])
                    if not content:
                        continue
                    
                    # Check if this is an earnings release
                    content_lower = content.lower()
                    is_earnings = any(kw in content_lower for kw in [
                        'earnings release', 'financial results', 'quarterly results',
                        'press release', 'results for the', 'fiscal year',
                    ])
                    
                    if not is_earnings:
                        continue
                    
                    # Clean and extract
                    soup = BeautifulSoup(content, 'html.parser')
                    text = soup.get_text(separator='\n', strip=True)
                    
                    transcripts.append({
                        'symbol': symbol,
                        'source': 'sec_8k',
                        'url': filing['filing_url'],
                        'title': f"{symbol} Earnings Release",
                        'date': filing['filing_date'],
                        'content': text[:20000],  # Limit length
                        'qa_section': '',  # 8-Ks don't have Q&A
                        'quarter': self._infer_quarter(filing['filing_date']),
                        'filing_type': '8-K',
                    })
                    
                except Exception as e:
                    logger.warning(f"Failed to process 8-K for {symbol}: {e}")
                    continue
        
        except Exception as e:
            logger.warning(f"Failed to fetch SEC earnings releases for {symbol}: {e}")
        
        return transcripts
    
    def _extract_date_from_title(self, title: str) -> str:
        """Extract date from transcript title."""
        # Patterns like "Q1 2024 Earnings Call" or "Q1 2024 Results"
        patterns = [
            r'Q[1-4]\s+(\d{4})',
            r'(\d{4})\s+Q[1-4]',
            r'(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),?\s+(\d{4})',
            r'(\d{1,2})/(\d{1,2})/(\d{4})',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, title, re.IGNORECASE)
            if match:
                if 'Q' in title.upper():
                    # Extract quarter and year
                    q_match = re.search(r'Q([1-4])\s+(\d{4})', title, re.IGNORECASE)
                    if q_match:
                        quarter = int(q_match.group(1))
                        year = int(q_match.group(2))
                        # Approximate date (middle of quarter)
                        month = quarter * 3
                        return f"{year}-{month:02d}-15"
                else:
                    # Try to parse full date
                    try:
                        from datetime import datetime
                        dt = datetime.strptime(match.group(0), '%B %d, %Y')
                        return dt.strftime('%Y-%m-%d')
                    except:
                        pass
        
        return datetime.now().strftime('%Y-%m-%d')
    
    def _extract_date_from_html(self, html: str) -> str:
        """Extract date from transcript HTML."""
        soup = BeautifulSoup(html, 'html.parser')
        
        # Look for time tags or date metadata
        time_tag = soup.find('time')
        if time_tag:
            datetime_attr = time_tag.get('datetime', '')
            if datetime_attr:
                return datetime_attr[:10]
        
        # Look for date in meta tags
        meta_date = soup.find('meta', property='article:published_time')
        if meta_date:
            return meta_date.get('content', '')[:10]
        
        return datetime.now().strftime('%Y-%m-%d')
    
    def _extract_qa(self, content: str) -> str:
        """Extract Q&A section from transcript."""
        qa_markers = [
            'question-and-answer session',
            'questions and answers',
            'q&a session',
            'operator: our next question',
            'operator: we will now begin',
        ]
        
        content_lower = content.lower()
        for marker in qa_markers:
            idx = content_lower.find(marker)
            if idx != -1:
                return content[idx:]
        
        # Fallback: look for analyst names
        analyst_pattern = re.search(r'(?:analyst|operator).*?:\s*(?:question|next)', content_lower)
        if analyst_pattern:
            return content[analyst_pattern.start():]
        
        return ''
    
    def _infer_quarter(self, date_str: str) -> str:
        """Infer fiscal quarter from date."""
        try:
            dt = datetime.strptime(date_str[:10], '%Y-%m-%d')
            month = dt.month
            if month <= 3:
                return f"Q1 {dt.year}"
            elif month <= 6:
                return f"Q2 {dt.year}"
            elif month <= 9:
                return f"Q3 {dt.year}"
            else:
                return f"Q4 {dt.year}"
        except:
            return ''
    
    def _save_transcript(self, transcript: Dict[str, Any]) -> Path:
        """Save transcript to storage."""
        symbol = transcript['symbol']
        symbol_dir = self.storage_dir / symbol
        symbol_dir.mkdir(exist_ok=True)
        
        date = transcript.get('date', datetime.now().strftime('%Y-%m-%d'))
        quarter = transcript.get('quarter', '')
        source = transcript.get('source', 'unknown')
        
        filename = f"transcript_{source}_{date}_{quarter}.json"
        filepath = symbol_dir / filename
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(transcript, f, indent=2, ensure_ascii=False)
        
        return filepath
    
    def load_saved_transcripts(self, symbol: str) -> List[Dict[str, Any]]:
        """Load previously saved transcripts."""
        symbol_dir = self.storage_dir / symbol
        if not symbol_dir.exists():
            return []
        
        transcripts = []
        for filepath in symbol_dir.glob('transcript_*.json'):
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    transcript = json.load(f)
                transcripts.append(transcript)
            except Exception as e:
                logger.warning(f"Failed to load transcript {filepath}: {e}")
        
        transcripts.sort(key=lambda x: x.get('date', ''), reverse=True)
        return transcripts
