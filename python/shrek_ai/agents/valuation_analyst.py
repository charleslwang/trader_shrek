"""
Valuation Analyst LLM agent
"""

from typing import Dict, Any, Optional
from pathlib import Path
import json
from loguru import logger

from ..config import get_llm_config
from ..llm import LLMClient


class ValuationAnalyst:
    """LLM agent for valuation analysis"""
    
    def __init__(self):
        self.llm_config = get_llm_config()
        self.llm = LLMClient(
            runtime=self.llm_config.get('runtime', 'ollama'),
            base_url=self.llm_config['base_url'],
            model=self.llm_config['model'],
        )
        self.prompt_path = Path(__file__).parent.parent.parent / 'prompts' / 'valuation_analyst.md'
    
    def analyze_valuation(
        self,
        symbol: str,
        financial_data: Dict[str, Any],
        peer_data: Optional[Dict[str, Any]] = None,
        historical_data: Optional[Dict[str, Any]] = None,
        additional_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Analyze valuation and provide scenario assumptions.
        
        Args:
            symbol: Stock symbol
            financial_data: Current financial data
            peer_data: Peer company data
            historical_data: Historical valuation data
            additional_context: Additional context
        
        Returns:
            Valuation analysis results
        """
        # Load prompt template
        with open(self.prompt_path, 'r') as f:
            prompt_template = f.read()
        
        # Format prompt
        prompt = prompt_template.format(symbol=symbol)
        
        # Add financial data
        prompt += f"\n\n## Financial Data\n\n{json.dumps(financial_data, indent=2)}"
        
        # Add peer data if available
        if peer_data:
            prompt += f"\n\n## Peer Data\n\n{json.dumps(peer_data, indent=2)}"
        
        # Add historical data if available
        if historical_data:
            prompt += f"\n\n## Historical Data\n\n{json.dumps(historical_data, indent=2)}"
        
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
        
        # Validate assumptions
        validated = self.validate_assumptions(analysis)
        
        return validated
    
    def validate_assumptions(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate valuation assumptions.
        
        Args:
            analysis: Valuation analysis results
        
        Returns:
            Validated analysis
        """
        valuation_assumptions = analysis.get('valuation_assumptions', {})
        
        for scenario in ['bear', 'base', 'bull']:
            if scenario in valuation_assumptions:
                scenario_data = valuation_assumptions[scenario]
                
                # Validate WACC > terminal growth
                wacc = scenario_data.get('wacc', 0)
                terminal_growth = scenario_data.get('terminal_growth', 0)
                
                if wacc <= terminal_growth:
                    logger.warning(f"{scenario} scenario: WACC ({wacc}) must be > terminal growth ({terminal_growth})")
                    # Adjust terminal growth
                    scenario_data['terminal_growth'] = max(0.01, wacc - 0.02)
                
                # Validate terminal growth in [0, 0.04]
                if not (0 <= terminal_growth <= 0.04):
                    logger.warning(f"{scenario} scenario: Terminal growth ({terminal_growth}) must be in [0, 0.04]")
                    scenario_data['terminal_growth'] = max(0, min(0.04, terminal_growth))
        
        return analysis
