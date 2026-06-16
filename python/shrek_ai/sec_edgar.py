"""
SEC EDGAR integration for filing retrieval and parsing
"""

from typing import List, Dict, Any, Optional
from pathlib import Path
from datetime import datetime, timedelta
import requests
from bs4 import BeautifulSoup
from loguru import logger
import time

from .config import get_sec_config


class SECEdgar:
    """SEC EDGAR filing retrieval and parsing"""
    
    BASE_URL = "https://www.sec.gov/cgi-bin/browse-edgar"
    FILINGS_URL = "https://www.sec.gov/Archives/edgar/data"
    
    def __init__(self):
        config = get_sec_config()
        self.user_agent = config['user_agent']
        self.headers = {
            'User-Agent': self.user_agent,
            'Accept': 'application/json',
        }
        self.rate_limit_delay = 0.1  # 10 requests per second
    
    def _make_request(self, url: str) -> Optional[requests.Response]:
        """Make request with rate limiting and error handling"""
        time.sleep(self.rate_limit_delay)
        
        try:
            response = requests.get(url, headers=self.headers, timeout=30)
            response.raise_for_status()
            return response
        except Exception as e:
            logger.error(f"Failed to fetch {url}: {e}")
            return None
    
    def get_company_ticker(self, symbol: str) -> Optional[str]:
        """Get CIK for a symbol"""
        # SEC ticker to CIK mapping
        ticker_url = f"https://www.sec.gov/files/company_tickers.json"
        response = self._make_request(ticker_url)
        
        if not response:
            return None
        
        data = response.json()
        
        for ticker_data in data.values():
            if ticker_data['ticker'].upper() == symbol.upper():
                return str(ticker_data['cik_str']).zfill(10)
        
        logger.warning(f"CIK not found for symbol {symbol}")
        return None
    
    def get_filings(
        self,
        symbol: str,
        filing_type: Optional[str] = None,
        count: int = 10,
    ) -> List[Dict[str, Any]]:
        """Get recent filings for a company"""
        cik = self.get_company_ticker(symbol)
        if not cik:
            return []
        
        params = {
            'CIK': cik,
            'type': filing_type if filing_type else '',
            'count': count,
            'owner': 'exclude',
        }
        
        url = f"{self.BASE_URL}?action=getcompany"
        response = self._make_request(f"{url}&{'&'.join(f'{k}={v}' for k, v in params.items())}")
        
        if not response:
            return []
        
        filings = []
        soup = BeautifulSoup(response.text, 'html.parser')
        
        table = soup.find('table', class_='tableFile2')
        if not table:
            return filings
        
        rows = table.find_all('tr')[1:]  # Skip header
        
        for row in rows:
            cells = row.find_all('td')
            if len(cells) < 5:
                continue
            
            filing_link = cells[2].find('a')
            if not filing_link:
                continue
            
            filing_url = f"https://www.sec.gov{filing_link['href']}"
            accession_number = cells[3].text.strip()
            filing_date = cells[4].text.strip()
            
            filings.append({
                'symbol': symbol,
                'cik': cik,
                'filing_type': cells[0].text.strip(),
                'filing_url': filing_url,
                'accession_number': accession_number,
                'filing_date': filing_date,
            })
        
        return filings
    
    def get_filing_content(self, filing_url: str) -> Optional[str]:
        """Get filing content from URL"""
        response = self._make_request(filing_url)
        
        if not response:
            return None
        
        # Navigate to the actual document
        soup = BeautifulSoup(response.text, 'html.parser')
        table = soup.find('table', class_='tableFile')
        
        if not table:
            return response.text
        
        # Find the main document (usually .htm or .txt)
        rows = table.find_all('tr')[1:]
        for row in rows:
            cells = row.find_all('td')
            if len(cells) < 3:
                continue
            
            doc_link = cells[2].find('a')
            if not doc_link:
                continue
            
            doc_url = f"https://www.sec.gov{doc_link['href']}"
            
            # Prefer .htm files over .txt
            if doc_url.endswith('.htm'):
                doc_response = self._make_request(doc_url)
                if doc_response:
                    return doc_response.text
        
        # Fallback to first document
        if rows:
            first_doc_link = rows[0].find_all('td')[2].find('a')
            if first_doc_link:
                doc_url = f"https://www.sec.gov{first_doc_link['href']}"
                doc_response = self._make_request(doc_url)
                if doc_response:
                    return doc_response.text
        
        return None
    
    def get_company_facts(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get company facts from SEC API"""
        cik = self.get_company_ticker(symbol)
        if not cik:
            return None
        
        url = f"https://data.sec.gov/submissions/CIK{cik}.json"
        response = self._make_request(url)
        
        if not response:
            return None
        
        return response.json()
    
    def get_10k(self, symbol: str, year: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """Get most recent 10-K filing"""
        filings = self.get_filings(symbol, filing_type='10-K', count=5)
        
        if not filings:
            return None
        
        # Filter by year if specified
        if year:
            filings = [f for f in filings if str(year) in f['filing_date']]
        
        if not filings:
            return None
        
        filing = filings[0]
        content = self.get_filing_content(filing['filing_url'])
        
        if not content:
            return None
        
        return {
            'symbol': symbol,
            'filing_type': '10-K',
            'filing_date': filing['filing_date'],
            'accession_number': filing['accession_number'],
            'content': content,
        }
    
    def get_10q(self, symbol: str, count: int = 4) -> List[Dict[str, Any]]:
        """Get recent 10-Q filings"""
        filings = self.get_filings(symbol, filing_type='10-Q', count=count)
        
        results = []
        for filing in filings:
            content = self.get_filing_content(filing['filing_url'])
            if content:
                results.append({
                    'symbol': symbol,
                    'filing_type': '10-Q',
                    'filing_date': filing['filing_date'],
                    'accession_number': filing['accession_number'],
                    'content': content,
                })
        
        return results
    
    def get_8k(self, symbol: str, count: int = 10) -> List[Dict[str, Any]]:
        """Get recent 8-K filings"""
        filings = self.get_filings(symbol, filing_type='8-K', count=count)
        
        results = []
        for filing in filings:
            content = self.get_filing_content(filing['filing_url'])
            if content:
                results.append({
                    'symbol': symbol,
                    'filing_type': '8-K',
                    'filing_date': filing['filing_date'],
                    'accession_number': filing['accession_number'],
                    'content': content,
                })
        
        return results
    
    def save_filing(self, filing: Dict[str, Any], output_dir: Path) -> Path:
        """Save filing to file"""
        output_dir.mkdir(parents=True, exist_ok=True)
        
        filename = f"{filing['symbol']}_{filing['filing_type']}_{filing['filing_date']}.txt"
        filepath = output_dir / filename
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(filing['content'])
        
        logger.info(f"Saved filing to {filepath}")
        return filepath
