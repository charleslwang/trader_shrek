"""
Content extraction and normalization utilities.
Handles HTML, PDF, and text content extraction with cleaning.
"""

import re
import io
from typing import Optional, Dict, Any, List
from pathlib import Path
from urllib.parse import urljoin, urlparse
from loguru import logger
import time
import requests
from bs4 import BeautifulSoup


class ContentExtractor:
    """Extract and normalize content from various sources."""
    
    def __init__(self, cache_dir: Optional[Path] = None, timeout: int = 30):
        self.cache_dir = cache_dir
        self.timeout = timeout
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
        }
        if cache_dir:
            cache_dir.mkdir(parents=True, exist_ok=True)
    
    def fetch_url(self, url: str, retries: int = 3, delay: float = 1.0) -> Optional[str]:
        """Fetch URL content with retries and caching."""
        # Check cache first
        if self.cache_dir:
            cache_key = self._url_to_cache_key(url)
            cache_path = self.cache_dir / cache_key
            if cache_path.exists():
                logger.debug(f"Cache hit for {url}")
                with open(cache_path, 'r', encoding='utf-8', errors='ignore') as f:
                    return f.read()
        
        for attempt in range(retries):
            try:
                time.sleep(delay * (attempt + 1))
                response = requests.get(url, headers=self.headers, timeout=self.timeout, allow_redirects=True)
                response.raise_for_status()
                content = response.text
                
                # Cache result
                if self.cache_dir:
                    cache_key = self._url_to_cache_key(url)
                    cache_path = self.cache_dir / cache_key
                    with open(cache_path, 'w', encoding='utf-8') as f:
                        f.write(content)
                
                return content
            except Exception as e:
                logger.warning(f"Failed to fetch {url} (attempt {attempt + 1}/{retries}): {e}")
                if attempt == retries - 1:
                    return None
        return None
    
    def extract_from_html(self, html: str, base_url: str = '') -> Dict[str, Any]:
        """Extract structured content from HTML."""
        soup = BeautifulSoup(html, 'html.parser')
        
        # Remove script and style elements
        for script in soup.find_all(['script', 'style', 'nav', 'footer', 'header']):
            script.decompose()
        
        # Extract title
        title = ''
        title_tag = soup.find('title')
        if title_tag:
            title = title_tag.get_text(strip=True)
        
        # Extract meta description
        description = ''
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        if meta_desc:
            description = meta_desc.get('content', '')
        
        # Extract article content (prioritize article/main tags)
        content = ''
        for selector in ['article', 'main', '.article-body', '.content', '.post-content', '#content', 'body']:
            element = soup.select_one(selector)
            if element:
                content = element.get_text(separator='\n', strip=True)
                break
        
        # Extract links
        links = []
        for a in soup.find_all('a', href=True):
            href = a['href']
            full_url = urljoin(base_url, href)
            links.append({
                'url': full_url,
                'text': a.get_text(strip=True),
                'is_pdf': href.lower().endswith('.pdf'),
                'is_external': not urlparse(full_url).netloc.endswith(urlparse(base_url).netloc) if base_url else True,
            })
        
        # Extract PDF links specifically
        pdf_links = [l for l in links if l['is_pdf']]
        
        return {
            'title': title,
            'description': description,
            'content': content,
            'links': links,
            'pdf_links': pdf_links,
            'url': base_url,
        }
    
    def extract_from_pdf_url(self, pdf_url: str) -> Optional[str]:
        """Extract text from a PDF URL."""
        try:
            import PyPDF2
        except ImportError:
            logger.warning("PyPDF2 not installed, attempting fallback extraction")
            return self._fallback_pdf_extract(pdf_url)
        
        try:
            time.sleep(0.5)  # Rate limit
            response = requests.get(pdf_url, headers=self.headers, timeout=self.timeout)
            response.raise_for_status()
            
            pdf_file = io.BytesIO(response.content)
            reader = PyPDF2.PdfReader(pdf_file)
            
            text = []
            for page_num, page in enumerate(reader.pages):
                try:
                    page_text = page.extract_text()
                    if page_text:
                        text.append(f"--- Page {page_num + 1} ---\n{page_text}")
                except Exception as e:
                    logger.warning(f"Failed to extract page {page_num + 1} from {pdf_url}: {e}")
            
            return '\n\n'.join(text)
        except Exception as e:
            logger.warning(f"Failed to extract PDF from {pdf_url}: {e}")
            return None
    
    def _fallback_pdf_extract(self, pdf_url: str) -> Optional[str]:
        """Fallback PDF extraction using external tools or text extraction."""
        try:
            # Try using pdftotext if available
            import subprocess
            import tempfile
            
            time.sleep(0.5)
            response = requests.get(pdf_url, headers=self.headers, timeout=self.timeout)
            
            with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
                tmp.write(response.content)
                tmp_path = tmp.name
            
            result = subprocess.run(
                ['pdftotext', tmp_path, '-'],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            import os
            os.unlink(tmp_path)
            
            if result.returncode == 0:
                return result.stdout
            return None
        except Exception:
            return None
    
    def clean_text(self, text: str) -> str:
        """Clean extracted text."""
        if not text:
            return ''
        
        # Remove excessive whitespace
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = re.sub(r'[ \t]+', ' ', text)
        
        # Remove common noise patterns
        text = re.sub(r'\bCookie Policy\b.*', '', text, flags=re.IGNORECASE)
        text = re.sub(r'\bPrivacy Policy\b.*', '', text, flags=re.IGNORECASE)
        text = re.sub(r'\bTerms of Use\b.*', '', text, flags=re.IGNORECASE)
        
        # Remove email addresses and phone numbers (often footer noise)
        text = re.sub(r'\S+@\S+', '', text)
        text = re.sub(r'\+?\d{1,3}[-.\s]?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', '', text)
        
        return text.strip()
    
    def extract_tables_from_html(self, html: str) -> List[Dict[str, Any]]:
        """Extract tables from HTML as structured data."""
        soup = BeautifulSoup(html, 'html.parser')
        tables = []
        
        for i, table in enumerate(soup.find_all('table')):
            rows = []
            for tr in table.find_all('tr'):
                row_data = []
                for cell in tr.find_all(['td', 'th']):
                    row_data.append(cell.get_text(strip=True))
                if row_data:
                    rows.append(row_data)
            
            if rows:
                tables.append({
                    'index': i,
                    'rows': rows,
                    'headers': rows[0] if rows else [],
                })
        
        return tables
    
    def _url_to_cache_key(self, url: str) -> str:
        """Convert URL to safe cache filename."""
        import hashlib
        return hashlib.md5(url.encode()).hexdigest() + '.html'
