"""
Earnings transcript processing
"""

from typing import Dict, Any, Optional, List
from pathlib import Path
import json
import re
from loguru import logger


class TranscriptManager:
    """Manage earnings transcripts"""
    
    def __init__(self, storage_dir: Path):
        self.storage_dir = storage_dir
        self.storage_dir.mkdir(parents=True, exist_ok=True)
    
    def save_transcript(
        self,
        symbol: str,
        quarter: str,
        year: int,
        transcript_content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Path:
        """
        Save earnings transcript.
        
        Args:
            symbol: Stock symbol
            quarter: Quarter (Q1, Q2, Q3, Q4)
            year: Year
            transcript_content: Transcript text
            metadata: Optional metadata
        
        Returns:
            Path to saved file
        """
        symbol_dir = self.storage_dir / symbol
        symbol_dir.mkdir(exist_ok=True)
        
        filename = f"transcript_{quarter}_{year}.txt"
        filepath = symbol_dir / filename
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(transcript_content)
        
        # Save metadata
        if metadata:
            metadata_path = filepath.with_suffix('.json')
            with open(metadata_path, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2, default=str)
        
        logger.info(f"Saved transcript for {symbol} {quarter} {year}")
        return filepath
    
    def load_transcript(
        self,
        symbol: str,
        quarter: str,
        year: int,
    ) -> Optional[Dict[str, Any]]:
        """
        Load earnings transcript.
        
        Args:
            symbol: Stock symbol
            quarter: Quarter
            year: Year
        
        Returns:
            Transcript data or None
        """
        symbol_dir = self.storage_dir / symbol
        filename = f"transcript_{quarter}_{year}.txt"
        filepath = symbol_dir / filename
        
        if not filepath.exists():
            return None
        
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        metadata_path = filepath.with_suffix('.json')
        metadata = {}
        if metadata_path.exists():
            with open(metadata_path, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
        
        return {
            'symbol': symbol,
            'quarter': quarter,
            'year': year,
            'content': content,
            'metadata': metadata,
        }
    
    def list_transcripts(self, symbol: str) -> List[Dict[str, Any]]:
        """
        List all transcripts for a symbol.
        
        Args:
            symbol: Stock symbol
        
        Returns:
            List of transcript metadata
        """
        symbol_dir = self.storage_dir / symbol
        
        if not symbol_dir.exists():
            return []
        
        transcripts = []
        for metadata_file in symbol_dir.glob('transcript_*.json'):
            with open(metadata_file, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
            transcripts.append(metadata)
        
        # Sort by date descending
        transcripts.sort(key=lambda x: x.get('date', ''), reverse=True)
        
        return transcripts
    
    def extract_qa_section(self, transcript: str) -> str:
        """
        Extract Q&A section from transcript.
        
        Args:
            transcript: Full transcript text
        
        Returns:
            Q&A section text
        """
        # Look for Q&A section markers
        qa_markers = [
            'Q&A',
            'Question and Answer',
            'QUESTIONS AND ANSWERS',
            'Q & A',
        ]
        
        lines = transcript.split('\n')
        qa_start = -1
        
        for i, line in enumerate(lines):
            if any(marker in line.upper() for marker in qa_markers):
                qa_start = i
                break
        
        if qa_start == -1:
            logger.warning("Could not find Q&A section in transcript")
            return transcript
        
        return '\n'.join(lines[qa_start:])
    
    def extract_management_guidance(self, transcript: str) -> Dict[str, Any]:
        """
        Extract management guidance from transcript using keyword heuristics.

        Args:
            transcript: Transcript text

        Returns:
            Dictionary of guidance items
        """
        text_lower = transcript.lower()
        guidance = {}

        # Revenue guidance
        rev_patterns = [
            r'(?:revenue|sales)\s+(?:guidance|outlook|expected)\s*[\$]?\s*([\d,]+(?:\.\d+)?)\s*(?:million|billion)?',
            r'(?:expect|project|guide)\s+(?:revenue|sales)\s*(?:of\s+)?[\$]?\s*([\d,]+(?:\.\d+)?)',
        ]
        for pat in rev_patterns:
            m = re.search(pat, text_lower)
            if m:
                try:
                    guidance['revenue_guidance'] = float(m.group(1).replace(',', ''))
                    break
                except (ValueError, IndexError):
                    continue

        # EPS guidance
        eps_patterns = [
            r'(?:eps|earnings per share)\s+(?:guidance|outlook|expected)\s*\$?\s*([\d,]+(?:\.\d+)?)',
            r'(?:expect|project|guide)\s+(?:eps|earnings per share)\s*(?:of\s+)?\$?\s*([\d,]+(?:\.\d+)?)',
        ]
        for pat in eps_patterns:
            m = re.search(pat, text_lower)
            if m:
                try:
                    guidance['eps_guidance'] = float(m.group(1).replace(',', ''))
                    break
                except (ValueError, IndexError):
                    continue

        # Margin guidance
        margin_patterns = [
            r'(?:gross|operating)\s+margin\s+(?:guidance|expected|target)\s*([\d,]+(?:\.\d+)?)%?',
        ]
        for pat in margin_patterns:
            m = re.search(pat, text_lower)
            if m:
                try:
                    val = float(m.group(1).replace(',', ''))
                    if val > 1:
                        val = val / 100.0
                    guidance['margin_guidance'] = val
                    break
                except (ValueError, IndexError):
                    continue

        # Detect guidance stance from surrounding language
        if guidance:
            raise_words = ['raise', 'increase', 'raise guidance', 'raise outlook', 'upward', 'higher']
            cut_words = ['cut', 'lower', 'decrease', 'reduce', 'lower guidance', 'downward', 'lower outlook']
            if any(w in text_lower for w in raise_words):
                guidance['guidance_stance'] = 'raise'
            elif any(w in text_lower for w in cut_words):
                guidance['guidance_stance'] = 'cut'
            else:
                guidance['guidance_stance'] = 'maintain'

        return guidance
