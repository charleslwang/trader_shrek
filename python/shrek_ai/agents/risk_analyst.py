"""
Risk Analyst LLM agent
"""

from typing import Dict, Any, Optional
from pathlib import Path
import json
from loguru import logger

from ..config import get_llm_config
from ..llm import LLMClient


class RiskAnalyst:
    """LLM agent for risk analysis"""
    
    def __init__(self):
        self.llm_config = get_llm_config()
        self.llm = LLMClient(
            base_url=self.llm_config['base_url'],
            model=self.llm_config['model'],
        )
        self.prompt_path = Path(__file__).parent.parent.parent / 'prompts' / 'risk_analyst.md'
    
    def analyze_risk(
        self,
        symbol: str,
        financial_data: Dict[str, Any],
        filing_analysis: Optional[Dict[str, Any]] = None,
        news: Optional[list[Dict[str, Any]]] = None,
        additional_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Analyze risks for a company.
        
        Args:
            symbol: Stock symbol
            financial_data: Financial data
            filing_analysis: Filing analysis results
            news: Recent news articles
            additional_context: Additional context
        
        Returns:
            Risk analysis results
        """
        # Load prompt template
        with open(self.prompt_path, 'r') as f:
            prompt_template = f.read()
        
        # Format prompt
        prompt = prompt_template.format(symbol=symbol)
        
        # Add financial data
        prompt += f"\n\n## Financial Data\n\n{json.dumps(financial_data, indent=2)}"
        
        # Add filing analysis if available
        if filing_analysis:
            prompt += f"\n\n## Filing Analysis\n\n{json.dumps(filing_analysis, indent=2)}"
        
        # Add news if available
        if news:
            prompt += f"\n\n## Recent News\n\n{json.dumps(news[:5], indent=2)}"
        
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
    
    def calculate_risk_score(self, analysis: Dict[str, Any]) -> float:
        """
        Calculate overall risk score from analysis.
        
        Args:
            analysis: Risk analysis results
        
        Returns:
            Risk score (0 to 1, higher is worse)
        """
        risk_components = [
            analysis.get('red_flags', []),
            analysis.get('balance_sheet_risks', []),
            analysis.get('valuation_risks', []),
            analysis.get('dilution_risks', []),
            analysis.get('regulatory_risks', []),
            analysis.get('competitive_risks', []),
            analysis.get('accounting_risks', []),
        ]
        
        # Count high-severity risks
        high_severity_count = 0
        total_risks = 0
        
        for component in risk_components:
            for risk in component:
                total_risks += 1
                if risk.get('severity') == 'high':
                    high_severity_count += 1
        
        if total_risks == 0:
            return 0.0
        
        # Risk score based on proportion of high-severity risks
        risk_score = min(1.0, high_severity_count / max(1, total_risks / 2))
        
        return risk_score
