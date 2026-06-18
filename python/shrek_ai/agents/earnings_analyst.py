"""
Earnings Analyst LLM agent
"""

from typing import Dict, Any, Optional
from pathlib import Path
import json
from loguru import logger

from ..config import get_llm_config
from ..llm import LLMClient


class EarningsAnalyst:
    """LLM agent for earnings analysis"""
    
    def __init__(self):
        self.llm_config = get_llm_config()
        self.llm = LLMClient(
            runtime=self.llm_config.get('runtime', 'ollama'),
            base_url=self.llm_config['base_url'],
            model=self.llm_config['model'],
        )
        self.prompt_path = Path(__file__).parent.parent.parent / 'prompts' / 'earnings_analyst.md'
    
    def analyze_earnings(
        self,
        symbol: str,
        fiscal_period: str,
        earnings_release: str,
        transcript: Optional[str] = None,
        guidance: Optional[str] = None,
        additional_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Analyze earnings release and transcript.
        
        Args:
            symbol: Stock symbol
            fiscal_period: Fiscal period
            earnings_release: Earnings release text
            transcript: Optional earnings transcript
            guidance: Optional guidance text
            additional_context: Additional context
        
        Returns:
            Analysis results
        """
        # Load prompt template
        with open(self.prompt_path, 'r') as f:
            prompt_template = f.read()
        
        # Format prompt
        prompt = prompt_template.format(
            symbol=symbol,
            fiscal_period=fiscal_period,
        )
        
        # Add earnings release
        prompt += f"\n\n## Earnings Release\n\n{earnings_release[:5000]}"
        
        # Add transcript if available
        if transcript:
            prompt += f"\n\n## Earnings Transcript\n\n{transcript[:5000]}"
        
        # Add guidance if available
        if guidance:
            prompt += f"\n\n## Guidance\n\n{guidance}"
        
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
                'fiscal_period': fiscal_period,
                'error': 'Failed to parse response',
            }
        
        return analysis
    
    def extract_thesis_events(self, analysis: Dict[str, Any]) -> list[Dict[str, Any]]:
        """
        Extract thesis events from analysis.
        
        Args:
            analysis: Earnings analysis results
        
        Returns:
            List of thesis events
        """
        events = []
        
        # Convert stance to events
        guidance_stance = analysis.get('guidance_stance', 'neutral')
        if guidance_stance == 'strong raise':
            events.append({
                'event': 'Guidance raised strongly',
                'score': 0.4,
                'reliability': 0.9,
                'source_id': 'earnings_analysis',
            })
        elif guidance_stance == 'moderate raise':
            events.append({
                'event': 'Guidance raised moderately',
                'score': 0.25,
                'reliability': 0.8,
                'source_id': 'earnings_analysis',
            })
        elif guidance_stance == 'moderate cut':
            events.append({
                'event': 'Guidance cut moderately',
                'score': -0.25,
                'reliability': 0.8,
                'source_id': 'earnings_analysis',
            })
        elif guidance_stance == 'severe cut':
            events.append({
                'event': 'Guidance cut severely',
                'score': -0.45,
                'reliability': 0.9,
                'source_id': 'earnings_analysis',
            })
        
        return events
