"""
Filing storage and management
"""

from typing import List, Dict, Any, Optional
from pathlib import Path
import json
from datetime import datetime
from loguru import logger

from .sec_edgar import SECEdgar


class FilingManager:
    """Manage SEC filings storage and retrieval"""
    
    def __init__(self, storage_dir: Path):
        self.storage_dir = storage_dir
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.edgar = SECEdgar()
    
    def download_filings(
        self,
        symbol: str,
        filing_types: List[str],
        count: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Download filings for a symbol.
        
        Args:
            symbol: Stock symbol
            filing_types: List of filing types to download
            count: Number of filings to download per type
        
        Returns:
            List of downloaded filings
        """
        downloaded = []
        
        for filing_type in filing_types:
            filings = self.edgar.get_filings(symbol, filing_type=filing_type, count=count)
            
            for filing in filings:
                content = self.edgar.get_filing_content(filing['filing_url'])
                
                if content:
                    filing['content'] = content
                    filepath = self.save_filing(filing)
                    filing['local_path'] = str(filepath)
                    downloaded.append(filing)
        
        logger.info(f"Downloaded {len(downloaded)} filings for {symbol}")
        return downloaded
    
    def save_filing(self, filing: Dict[str, Any]) -> Path:
        """
        Save filing to local storage.
        
        Args:
            filing: Filing data
        
        Returns:
            Path to saved file
        """
        symbol_dir = self.storage_dir / filing['symbol']
        symbol_dir.mkdir(exist_ok=True)
        
        filename = f"{filing['filing_type']}_{filing['filing_date']}.txt"
        filepath = symbol_dir / filename
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(filing['content'])
        
        # Save metadata
        metadata_path = filepath.with_suffix('.json')
        metadata = {k: v for k, v in filing.items() if k != 'content'}
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, default=str)
        
        return filepath
    
    def load_filing(self, symbol: str, filing_type: str, filing_date: str) -> Optional[Dict[str, Any]]:
        """
        Load filing from local storage.
        
        Args:
            symbol: Stock symbol
            filing_type: Filing type
            filing_date: Filing date
        
        Returns:
            Filing data or None
        """
        symbol_dir = self.storage_dir / symbol
        filename = f"{filing_type}_{filing_date}.txt"
        filepath = symbol_dir / filename
        
        if not filepath.exists():
            return None
        
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        metadata_path = filepath.with_suffix('.json')
        with open(metadata_path, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
        
        metadata['content'] = content
        return metadata
    
    def list_filings(self, symbol: str) -> List[Dict[str, Any]]:
        """
        List all filings for a symbol.
        
        Args:
            symbol: Stock symbol
        
        Returns:
            List of filing metadata
        """
        symbol_dir = self.storage_dir / symbol
        
        if not symbol_dir.exists():
            return []
        
        filings = []
        for metadata_file in symbol_dir.glob('*.json'):
            with open(metadata_file, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
            filings.append(metadata)
        
        # Sort by date descending
        filings.sort(key=lambda x: x['filing_date'], reverse=True)
        
        return filings
    
    def get_latest_10k(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get latest 10-K filing.
        
        Args:
            symbol: Stock symbol
        
        Returns:
            Latest 10-K or None
        """
        filings = self.list_filings(symbol)
        
        for filing in filings:
            if filing['filing_type'] == '10-K':
                return self.load_filing(symbol, '10-K', filing['filing_date'])
        
        return None
    
    def get_latest_10q(self, symbol: str, count: int = 4) -> List[Dict[str, Any]]:
        """
        Get latest 10-Q filings.
        
        Args:
            symbol: Stock symbol
            count: Number of 10-Qs to return
        
        Returns:
            List of 10-Q filings
        """
        filings = self.list_filings(symbol)
        
        ten_qs = []
        for filing in filings:
            if filing['filing_type'] == '10-Q':
                ten_q = self.load_filing(symbol, '10-Q', filing['filing_date'])
                if ten_q:
                    ten_qs.append(ten_q)
                if len(ten_qs) >= count:
                    break
        
        return ten_qs
