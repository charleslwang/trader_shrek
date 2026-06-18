"""
Alternative data sources.

Sources:
- USPTO patent search
- Job postings (Indeed, company careers pages)
- Google Trends
- Social media sentiment (if APIs available)
- Industry conference presentations
- Supplier/customer relationship data
"""

import re
import json
import time
from typing import Optional, Dict, Any, List
from pathlib import Path
from urllib.parse import quote
from datetime import datetime, timedelta
from loguru import logger
import requests
from bs4 import BeautifulSoup

from .content_extractor import ContentExtractor


class AlternativeDataFetcher:
    """Fetch alternative data signals for a company."""
    
    def __init__(self, cache_dir: Optional[Path] = None, storage_dir: Optional[Path] = None):
        self.cache_dir = cache_dir or Path('data/cache/alternative')
        self.storage_dir = storage_dir or Path('data/alternative')
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        
        self.extractor = ContentExtractor(cache_dir=self.cache_dir)
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        }
        self.rate_limit_delay = 1.0
    
    def get_alternative_data(self, symbol: str, company_name: str = '') -> Dict[str, Any]:
        """
        Get all alternative data for a symbol.
        
        Args:
            symbol: Stock symbol
            company_name: Full company name
        
        Returns:
            Dictionary with patents, job postings, trends, etc.
        """
        results = {
            'symbol': symbol,
            'patents': [],
            'job_postings': [],
            'trends': {},
            'signals': [],
            'consolidated_text': '',
        }
        
        # Fetch patents
        patents = self._fetch_uspto_patents(symbol, company_name)
        results['patents'] = patents
        
        # Fetch job postings
        jobs = self._fetch_job_postings(symbol, company_name)
        results['job_postings'] = jobs
        
        # Fetch Google Trends
        trends = self._fetch_google_trends(symbol, company_name)
        results['trends'] = trends
        
        # Generate signals
        results['signals'] = self._extract_signals(results)
        
        # Build consolidated text
        texts = []
        if patents:
            texts.append(f"Recent Patents ({len(patents)}): " + ", ".join([p['title'] for p in patents[:5]]))
        if jobs:
            texts.append(f"Recent Job Postings ({len(jobs)}): " + ", ".join([j['title'] for j in jobs[:10]]))
        if trends:
            texts.append(f"Google Trends: {json.dumps(trends)}")
        
        results['consolidated_text'] = '\n\n'.join(texts)
        
        logger.info(f"Fetched alternative data for {symbol}: {len(patents)} patents, {len(jobs)} jobs")
        return results
    
    def _fetch_uspto_patents(self, symbol: str, company_name: str) -> List[Dict[str, Any]]:
        """Fetch recent patents from USPTO."""
        patents = []
        
        if not company_name:
            logger.warning(f"No company name for {symbol}, skipping patent search")
            return patents
        
        try:
            # USPTO patent search API (Patent Public Search)
            search_term = quote(f'"{company_name}"')
            url = f"https://ppubs.uspto.gov/dirsearch-public/searches/patents?query={search_term}&page=1&pageSize=20"
            
            response = requests.get(url, headers=self.headers, timeout=15)
            if response.status_code == 200:
                data = response.json()
                
                for patent in data.get('patents', [])[:10]:
                    patents.append({
                        'symbol': symbol,
                        'source': 'uspto',
                        'patent_number': patent.get('patentNumber', ''),
                        'title': patent.get('title', ''),
                        'date': patent.get('publicationDate', ''),
                        'abstract': patent.get('abstract', '')[:1000],
                        'inventors': patent.get('inventors', []),
                        'url': f"https://patents.uspto.gov/patent/{patent.get('patentNumber', '')}",
                    })
        
        except Exception as e:
            logger.warning(f"Failed to fetch USPTO patents for {symbol}: {e}")
            # Fallback: try Google Patents
            patents = self._fetch_google_patents(symbol, company_name)
        
        return patents
    
    def _fetch_google_patents(self, symbol: str, company_name: str) -> List[Dict[str, Any]]:
        """Fallback: fetch patents from Google Patents."""
        patents = []
        
        try:
            search_term = quote(f'assignee:"{company_name}"')
            url = f"https://patents.google.com/?q={search_term}&type=PATENT"
            
            html = self.extractor.fetch_url(url, retries=2, delay=2.0)
            if not html:
                return patents
            
            soup = BeautifulSoup(html, 'html.parser')
            
            # Extract patent listings
            for result in soup.find_all('search-result-item')[:10]:
                title = result.get_text()[:200]
                patents.append({
                    'symbol': symbol,
                    'source': 'google_patents',
                    'title': title,
                    'date': '',
                    'abstract': '',
                })
        
        except Exception as e:
            logger.warning(f"Failed to fetch Google Patents for {symbol}: {e}")
        
        return patents
    
    def _fetch_job_postings(self, symbol: str, company_name: str) -> List[Dict[str, Any]]:
        """Fetch job postings from Indeed and company careers."""
        jobs = []
        
        # Try Indeed search
        if company_name:
            try:
                search_term = quote(company_name)
                url = f"https://www.indeed.com/jobs?q={search_term}&sort=date"
                
                html = self.extractor.fetch_url(url, retries=2, delay=2.0)
                if html:
                    soup = BeautifulSoup(html, 'html.parser')
                    
                    for job_card in soup.find_all('div', class_=re.compile('job_seen_beacon|slider_container'))[:15]:
                        title_elem = job_card.find('h2', class_=re.compile('jobTitle'))
                        title = title_elem.get_text(strip=True) if title_elem else ''
                        
                        company_elem = job_card.find('span', class_=re.compile('companyName'))
                        company = company_elem.get_text(strip=True) if company_elem else ''
                        
                        location_elem = job_card.find('div', class_=re.compile('companyLocation'))
                        location = location_elem.get_text(strip=True) if location_elem else ''
                        
                        summary_elem = job_card.find('div', class_=re.compile('job-snippet'))
                        summary = summary_elem.get_text(strip=True) if summary_elem else ''
                        
                        # Filter for relevant/technical jobs
                        is_technical = any(kw in title.lower() for kw in [
                            'engineer', 'scientist', 'developer', 'researcher',
                            'ai', 'machine learning', 'data', 'software',
                            'hardware', 'product manager', 'architect',
                        ])
                        
                        jobs.append({
                            'symbol': symbol,
                            'source': 'indeed',
                            'title': title,
                            'company': company,
                            'location': location,
                            'summary': summary[:500],
                            'is_technical': is_technical,
                            'date': datetime.now().strftime('%Y-%m-%d'),
                        })
            
            except Exception as e:
                logger.warning(f"Failed to fetch Indeed jobs for {symbol}: {e}")
        
        # Try company careers page
        if company_name:
            try:
                careers_jobs = self._fetch_company_careers(symbol, company_name)
                jobs.extend(careers_jobs)
            except Exception as e:
                logger.warning(f"Failed to fetch company careers for {symbol}: {e}")
        
        return jobs
    
    def _fetch_company_careers(self, symbol: str, company_name: str) -> List[Dict[str, Any]]:
        """Fetch jobs from company careers page."""
        jobs = []
        
        # Try common careers paths
        domain = self._guess_domain(company_name)
        if not domain:
            return jobs
        
        career_paths = ['/careers', '/jobs', '/careers/jobs', '/join', '/about/careers']
        
        for path in career_paths:
            try:
                url = f"https://{domain}{path}"
                html = self.extractor.fetch_url(url, retries=1, delay=1.0)
                if not html:
                    continue
                
                soup = BeautifulSoup(html, 'html.parser')
                text = soup.get_text()
                
                # Count job mentions
                job_keywords = ['engineer', 'scientist', 'manager', 'director', 'analyst']
                job_count = sum(text.lower().count(kw) for kw in job_keywords)
                
                if job_count > 5:
                    jobs.append({
                        'symbol': symbol,
                        'source': 'company_careers',
                        'title': f'Active hiring detected on careers page',
                        'company': company_name,
                        'location': '',
                        'summary': f'Found {job_count}+ job references on careers page. Keywords: engineer, scientist, manager.',
                        'is_technical': True,
                        'date': datetime.now().strftime('%Y-%m-%d'),
                    })
                    break
            
            except Exception as e:
                continue
        
        return jobs
    
    def _fetch_google_trends(self, symbol: str, company_name: str) -> Dict[str, Any]:
        """Fetch Google Trends data (if pytrends available)."""
        trends = {}
        
        try:
            from pytrends.request import TrendReq
            
            pytrends = TrendReq(hl='en-US', tz=360)
            
            keywords = [company_name] if company_name else [symbol]
            pytrends.build_payload(keywords, timeframe='today 3-m')
            
            interest = pytrends.interest_over_time()
            if not interest.empty:
                trends['interest_over_time'] = {
                    'current': float(interest[keywords[0]].iloc[-1]),
                    'average_3m': float(interest[keywords[0]].mean()),
                    'trend': 'increasing' if interest[keywords[0]].iloc[-1] > interest[keywords[0]].iloc[0] else 'decreasing',
                }
            
            # Related queries
            related = pytrends.related_queries()
            if related and keywords[0] in related:
                rising = related[keywords[0]].get('rising', {})
                if not rising.empty:
                    trends['rising_queries'] = rising.head(5).to_dict()
        
        except ImportError:
            logger.debug("pytrends not installed, skipping Google Trends")
        except Exception as e:
            logger.warning(f"Failed to fetch Google Trends for {symbol}: {e}")
        
        return trends
    
    def _extract_signals(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract investment signals from alternative data."""
        signals = []
        
        # Patent signals
        patents = data.get('patents', [])
        if len(patents) > 5:
            signals.append({
                'type': 'patent_acceleration',
                'score': min(len(patents) / 10, 1.0),
                'description': f'High patent activity: {len(patents)} recent patents',
                'direction': 'bullish',
            })
        
        # Technical hiring signals
        jobs = data.get('job_postings', [])
        tech_jobs = [j for j in jobs if j.get('is_technical', False)]
        if len(tech_jobs) > 10:
            signals.append({
                'type': 'hiring_acceleration',
                'score': min(len(tech_jobs) / 20, 1.0),
                'description': f'Accelerated technical hiring: {len(tech_jobs)} recent postings',
                'direction': 'bullish',
            })
        
        # Trend signals
        trends = data.get('trends', {})
        interest = trends.get('interest_over_time', {})
        if interest.get('trend') == 'increasing' and interest.get('current', 0) > 50:
            signals.append({
                'type': 'search_interest',
                'score': min(interest['current'] / 100, 1.0),
                'description': f'Rising Google search interest: {interest["current"]:.0f}/100',
                'direction': 'bullish',
            })
        
        return signals
    
    def _guess_domain(self, company_name: str) -> Optional[str]:
        """Guess company domain from name."""
        # Simple heuristic
        cleaned = re.sub(r'[^\w\s]', '', company_name).lower().replace(' ', '')
        
        common_tlds = ['.com', '.io', '.ai', '.co']
        for tld in common_tlds:
            domain = f"{cleaned}{tld}"
            try:
                response = requests.head(f"https://{domain}", headers=self.headers, timeout=5, allow_redirects=True)
                if response.status_code < 400:
                    return domain
            except:
                continue
        
        return None
