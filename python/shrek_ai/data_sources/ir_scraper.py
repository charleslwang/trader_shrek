"""
Investor Relations page scraper.

Scrapes company IR pages for:
- Investor presentations (PDFs)
- Earnings presentation slides
- Fact sheets
- Annual reports
- Proxy statements
- ESG reports
- Press releases from IR pages
"""

import re
import json
import time
from typing import Optional, Dict, Any, List
from pathlib import Path
from urllib.parse import urljoin, urlparse
from loguru import logger
import requests
from bs4 import BeautifulSoup

from .content_extractor import ContentExtractor


class IRScraper:
    """Scrape investor relations materials from company websites."""
    
    # Common IR page paths
    IR_PATHS = [
        '/investors',
        '/investor-relations',
        '/ir',
        '/investor',
        '/about/investors',
        '/company/investors',
        '/corporate/investors',
        '/investor-relations.html',
        '/investors.html',
    ]
    
    # Keywords for finding presentation PDFs
    PRESENTATION_KEYWORDS = [
        'presentation', 'earnings presentation', 'investor presentation',
        'corporate presentation', 'analyst day', 'investor day',
        'quarterly', 'q[1-4]', 'fact sheet', 'overview',
    ]
    
    def __init__(self, cache_dir: Optional[Path] = None, storage_dir: Optional[Path] = None):
        self.cache_dir = cache_dir or Path('data/cache/ir')
        self.storage_dir = storage_dir or Path('data/ir')
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        
        self.extractor = ContentExtractor(cache_dir=self.cache_dir)
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        }
        self.rate_limit_delay = 1.0
    
    def scrape_ir(self, symbol: str, company_name: str = '', domain: str = '') -> Dict[str, Any]:
        """
        Scrape investor relations materials for a company.
        
        Args:
            symbol: Stock symbol
            company_name: Full company name
            domain: Known company domain (e.g., nvidia.com)
        
        Returns:
            Dictionary with all extracted IR materials
        """
        results = {
            'symbol': symbol,
            'ir_url': None,
            'presentations': [],
            'fact_sheets': [],
            'press_releases': [],
            'presentations_text': '',
            'ir_page_text': '',
            'scraped_at': time.strftime('%Y-%m-%d %H:%M:%S'),
        }
        
        # Find company domain if not provided
        if not domain:
            domain = self._find_company_domain(symbol, company_name)
        
        if not domain:
            logger.warning(f"Could not find domain for {symbol}")
            return results
        
        # Find IR page
        ir_url = self._find_ir_page(domain)
        results['ir_url'] = ir_url
        
        if not ir_url:
            logger.warning(f"Could not find IR page for {symbol} at {domain}")
            return results
        
        # Scrape IR page content
        try:
            ir_html = self.extractor.fetch_url(ir_url, retries=2, delay=self.rate_limit_delay)
            if ir_html:
                extracted = self.extractor.extract_from_html(ir_html, ir_url)
                results['ir_page_text'] = self.extractor.clean_text(extracted['content'])
                
                # Find all PDF links
                pdf_links = extracted.get('pdf_links', [])
                
                # Also search for presentation links
                for link in extracted['links']:
                    if self._is_presentation_link(link):
                        pdf_links.append(link)
                
                # Process PDFs
                for pdf_link in pdf_links[:10]:  # Limit to 10 PDFs
                    try:
                        pdf_text = self.extractor.extract_from_pdf_url(pdf_link['url'])
                        if pdf_text:
                            presentation = {
                                'url': pdf_link['url'],
                                'title': pdf_link['text'] or 'Presentation',
                                'text': self.extractor.clean_text(pdf_text)[:15000],
                                'extracted_at': time.strftime('%Y-%m-%d %H:%M:%S'),
                            }
                            
                            # Categorize
                            title_lower = presentation['title'].lower()
                            if any(kw in title_lower for kw in ['fact', 'sheet', 'overview']):
                                results['fact_sheets'].append(presentation)
                            else:
                                results['presentations'].append(presentation)
                            
                            # Save to storage
                            self._save_ir_material(symbol, presentation)
                            
                            time.sleep(0.5)
                    except Exception as e:
                        logger.warning(f"Failed to extract PDF {pdf_link['url']}: {e}")
                        continue
        
        except Exception as e:
            logger.warning(f"Failed to scrape IR page for {symbol}: {e}")
        
        # Aggregate presentation text
        all_presentation_text = []
        for pres in results['presentations']:
            all_presentation_text.append(f"--- {pres['title']} ---\n{pres['text']}")
        results['presentations_text'] = '\n\n'.join(all_presentation_text)
        
        logger.info(f"Scraped IR for {symbol}: {len(results['presentations'])} presentations, {len(results['fact_sheets'])} fact sheets")
        return results
    
    def _find_company_domain(self, symbol: str, company_name: str) -> Optional[str]:
        """Find company website domain."""
        # Try common patterns
        patterns = [
            f"https://www.{symbol.lower()}.com",
            f"https://{symbol.lower()}.com",
        ]
        
        for url in patterns:
            try:
                response = requests.head(url, headers=self.headers, timeout=10, allow_redirects=True)
                if response.status_code < 400:
                    return urlparse(response.url).netloc
            except:
                continue
        
        # Try searching
        if company_name:
            try:
                search_url = f"https://duckduckgo.com/html/?q={company_name.replace(' ', '+')}+official+website"
                response = requests.get(search_url, headers=self.headers, timeout=10)
                soup = BeautifulSoup(response.text, 'html.parser')
                
                for link in soup.find_all('a', href=True):
                    href = link.get('href', '')
                    if href.startswith('http') and not 'duckduckgo' in href:
                        domain = urlparse(href).netloc
                        if domain and '.' in domain:
                            return domain
            except:
                pass
        
        return None
    
    def _find_ir_page(self, domain: str) -> Optional[str]:
        """Find the investor relations page URL."""
        base_url = f"https://{domain}"
        
        for path in self.IR_PATHS:
            url = f"{base_url}{path}"
            try:
                time.sleep(self.rate_limit_delay)
                response = requests.head(url, headers=self.headers, timeout=10, allow_redirects=True)
                if response.status_code < 400:
                    return response.url
            except:
                continue
        
        # Try scanning the homepage for IR links
        try:
            time.sleep(self.rate_limit_delay)
            response = requests.get(base_url, headers=self.headers, timeout=10)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            for link in soup.find_all('a', href=True):
                href = link.get('href', '').lower()
                text = link.get_text(strip=True).lower()
                
                if 'investor' in href or 'investor' in text:
                    full_url = urljoin(base_url, link['href'])
                    return full_url
        except:
            pass
        
        return None
    
    def _is_presentation_link(self, link: Dict[str, Any]) -> bool:
        """Check if a link is likely a presentation."""
        url = link.get('url', '').lower()
        text = link.get('text', '').lower()
        
        # Must be a PDF
        if not url.endswith('.pdf'):
            return False
        
        # Check keywords
        combined = f"{url} {text}"
        for keyword in self.PRESENTATION_KEYWORDS:
            if re.search(keyword, combined, re.IGNORECASE):
                return True
        
        return False
    
    def _save_ir_material(self, symbol: str, material: Dict[str, Any]) -> Path:
        """Save IR material to storage."""
        symbol_dir = self.storage_dir / symbol
        symbol_dir.mkdir(exist_ok=True)
        
        # Create safe filename from URL
        import hashlib
        url_hash = hashlib.md5(material['url'].encode()).hexdigest()[:8]
        filename = f"ir_{material['title'][:30]}_{url_hash}.json"
        filename = re.sub(r'[^\w\-_.]', '_', filename)
        
        filepath = symbol_dir / filename
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(material, f, indent=2, ensure_ascii=False)
        
        return filepath
    
    def load_saved_ir(self, symbol: str) -> List[Dict[str, Any]]:
        """Load previously scraped IR materials."""
        symbol_dir = self.storage_dir / symbol
        if not symbol_dir.exists():
            return []
        
        materials = []
        for filepath in symbol_dir.glob('ir_*.json'):
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    material = json.load(f)
                materials.append(material)
            except Exception as e:
                logger.warning(f"Failed to load IR material {filepath}: {e}")
        
        return materials
