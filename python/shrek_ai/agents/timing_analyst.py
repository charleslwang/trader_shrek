"""
Timing Analyst LLM agent
"""

from typing import Dict, Any, Optional
from pathlib import Path
import json
from loguru import logger

from ..config import get_llm_config
from ..llm import LLMClient


class TimingAnalyst:
    """LLM agent for technical timing analysis"""
    
    def __init__(self):
        self.llm_config = get_llm_config()
        self.llm = LLMClient(
            base_url=self.llm_config['base_url'],
            model=self.llm_config['model'],
        )
        self.prompt_path = Path(__file__).parent.parent.parent / 'prompts' / 'timing_analyst.md'
    
    def analyze_timing(
        self,
        symbol: str,
        price_data: Dict[str, Any],
        technical_indicators: Optional[Dict[str, Any]] = None,
        additional_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Analyze technical timing.
        
        Args:
            symbol: Stock symbol
            price_data: Current and historical price data
            technical_indicators: Technical indicator values
            additional_context: Additional context
        
        Returns:
            Timing analysis results
        """
        # Load prompt template
        with open(self.prompt_path, 'r') as f:
            prompt_template = f.read()
        
        # Format prompt
        prompt = prompt_template.format(symbol=symbol)
        
        # Add price data
        prompt += f"\n\n## Price Data\n\n{json.dumps(price_data, indent=2)}"
        
        # Add technical indicators if available
        if technical_indicators:
            prompt += f"\n\n## Technical Indicators\n\n{json.dumps(technical_indicators, indent=2)}"
        
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
                'error': 'Failed to parse response',
            }
        
        return analysis
