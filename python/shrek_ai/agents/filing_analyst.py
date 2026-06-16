"""
Filing Analyst LLM agent
"""

from typing import Dict, Any, Optional
from pathlib import Path
import json
from loguru import logger

from ..config import get_llm_config
from ..llm import LLMClient


class FilingAnalyst:
    """LLM agent for SEC filing analysis"""
    
    def __init__(self):
        self.llm_config = get_llm_config()
        self.llm = LLMClient(
            base_url=self.llm_config['base_url'],
            model=self.llm_config['model'],
        )
        self.prompt_path = Path(__file__).parent.parent.parent / 'prompts' / 'filing_analyst.md'
    
    def analyze_filing(
        self,
        symbol: str,
        filing_type: str,
        fiscal_period: str,
        filing_content: str,
        additional_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Analyze a SEC filing.
        
        Args:
            symbol: Stock symbol
            filing_type: Type of filing (10-K, 10-Q, 8-K)
            fiscal_period: Fiscal period
            filing_content: Filing text content
            additional_context: Additional context to include
        
        Returns:
            Analysis results
        """
        # Load prompt template
        with open(self.prompt_path, 'r') as f:
            prompt_template = f.read()
        
        # Format prompt with filing data
        prompt = prompt_template.format(
            symbol=symbol,
            filing_type=filing_type,
            fiscal_period=fiscal_period,
        )
        
        # Add filing content
        prompt += f"\n\n## Filing Content\n\n{filing_content[:10000]}"  # Limit content length
        
        # Add additional context if provided
        if additional_context:
            prompt += f"\n\n## Additional Context\n\n{json.dumps(additional_context, indent=2)}"
        
        # Call LLM
        response = self.llm.generate(prompt, require_json=True)
        
        # Parse JSON response
        try:
            analysis = json.loads(response)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}")
            analysis = {
                'symbol': symbol,
                'filing_type': filing_type,
                'fiscal_period': fiscal_period,
                'error': 'Failed to parse response',
            }
        
        return analysis
    
    def extract_thesis_events(self, analysis: Dict[str, Any]) -> list[Dict[str, Any]]:
        """
        Extract thesis events from analysis.
        
        Args:
            analysis: Filing analysis results
        
        Returns:
            List of thesis events
        """
        return analysis.get('thesis_events', [])
