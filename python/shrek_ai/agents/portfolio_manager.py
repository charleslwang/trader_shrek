"""
Portfolio Manager LLM agent
"""

from typing import Dict, Any, Optional
from pathlib import Path
import json
from loguru import logger

from ..config import get_llm_config
from ..llm import LLMClient
from ..decision_policy import normalize_agent_decision
from ..math import (
    expected_return,
    upside_downside_ratio,
    margin_of_safety,
    shrek_score,
    investability_gate,
)


class PortfolioManager:
    """LLM agent for portfolio management decisions"""
    
    def __init__(self):
        self.llm_config = get_llm_config()
        self.llm = LLMClient(
            runtime=self.llm_config.get('runtime', 'ollama'),
            base_url=self.llm_config['base_url'],
            model=self.llm_config['model'],
        )
        self.prompt_path = Path(__file__).parent.parent.parent / 'prompts' / 'portfolio_manager.md'
    
    def make_decision(
        self,
        symbol: str,
        filing_analysis: Optional[Dict[str, Any]] = None,
        earnings_analysis: Optional[Dict[str, Any]] = None,
        valuation_analysis: Optional[Dict[str, Any]] = None,
        risk_analysis: Optional[Dict[str, Any]] = None,
        timing_analysis: Optional[Dict[str, Any]] = None,
        mathematical_scores: Optional[Dict[str, Any]] = None,
        additional_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Make portfolio management decision.
        
        Args:
            symbol: Stock symbol
            filing_analysis: Filing analysis results
            earnings_analysis: Earnings analysis results
            valuation_analysis: Valuation analysis results
            risk_analysis: Risk analysis results
            timing_analysis: Timing analysis results
            mathematical_scores: Computed mathematical scores
            additional_context: Additional context
        
        Returns:
            Portfolio decision
        """
        # Load prompt template
        with open(self.prompt_path, 'r') as f:
            prompt_template = f.read()
        
        # Format prompt
        prompt = prompt_template.format(symbol=symbol)
        
        # Add agent analyses
        if filing_analysis:
            prompt += f"\n\n## Filing Analysis\n\n{json.dumps(filing_analysis, indent=2)}"
        
        if earnings_analysis:
            prompt += f"\n\n## Earnings Analysis\n\n{json.dumps(earnings_analysis, indent=2)}"
        
        if valuation_analysis:
            prompt += f"\n\n## Valuation Analysis\n\n{json.dumps(valuation_analysis, indent=2)}"
        
        if risk_analysis:
            prompt += f"\n\n## Risk Analysis\n\n{json.dumps(risk_analysis, indent=2)}"
        
        if timing_analysis:
            prompt += f"\n\n## Timing Analysis\n\n{json.dumps(timing_analysis, indent=2)}"
        
        # Add mathematical scores
        if mathematical_scores:
            prompt += f"\n\n## Mathematical Scores\n\n{json.dumps(mathematical_scores, indent=2)}"
        
        # Add additional context if provided
        if additional_context:
            prompt += f"\n\n## Additional Context\n\n{json.dumps(additional_context, indent=2)}"
        
        # Call LLM
        response = self.llm.generate(prompt, require_json=True)
        
        # Parse JSON response
        try:
            decision = json.loads(response)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}")
            decision = {
                'symbol': symbol,
                'decision': 'AVOID',
                'confidence': 0.0,
                'error': 'Failed to parse response',
            }
        
        # Validate decision against mathematical thresholds
        validated = self.validate_decision(decision, mathematical_scores)
        
        return validated
    
    def validate_decision(
        self,
        decision: Dict[str, Any],
        mathematical_scores: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Validate LLM decision against mathematical thresholds.
        
        Args:
            decision: LLM decision
            mathematical_scores: Computed mathematical scores
        
        Returns:
            Validated decision
        """
        if mathematical_scores is None:
            return decision
        
        decision = normalize_agent_decision(decision)
        decision_type = decision.get('decision', 'AVOID')
        
        # If LLM recommends CONVICTION_BUY, verify conviction criteria
        if decision_type == 'CONVICTION_BUY':
            secular_conviction = mathematical_scores.get('secular_conviction', 0)
            narrative_conviction = mathematical_scores.get('narrative_conviction', 0)
            risk_penalty = mathematical_scores.get('risk_penalty', 0)
            quality = mathematical_scores.get('quality', 0)
            thesis_probability = mathematical_scores.get('thesis_probability', 0)
            
            if not (secular_conviction >= 0.70 and narrative_conviction >= 0.70):
                logger.warning(f"LLM recommended CONVICTION_BUY but secular={secular_conviction:.2f}, narrative={narrative_conviction:.2f}")
                decision['decision'] = 'WATCH'
                decision['validation_override'] = 'Conviction scores below threshold for CONVICTION_BUY'
            elif risk_penalty > 0.55:
                logger.warning(f"LLM recommended CONVICTION_BUY but risk_penalty={risk_penalty:.2f} exceeds 0.55")
                decision['decision'] = 'WATCH'
                decision['validation_override'] = 'Risk too high for CONVICTION_BUY'
            elif quality < 0.60 or thesis_probability < 0.65:
                logger.warning(f"LLM recommended CONVICTION_BUY but quality={quality:.2f}, thesis_prob={thesis_probability:.2f}")
                decision['decision'] = 'WATCH'
                decision['validation_override'] = 'Quality/thesis too low for CONVICTION_BUY'
            else:
                # CONVICTION_BUY validated - ensure it maps to a buy for downstream
                decision['is_conviction'] = True
        
        # If LLM recommends normal buy, verify it passes investability gate
        elif decision_type in ['BUY_STARTER', 'ADD']:
            investable = investability_gate(
                expected_return=mathematical_scores.get('expected_return', 0),
                upside_downside=mathematical_scores.get('upside_downside', 0),
                quality=mathematical_scores.get('quality', 0),
                risk_penalty=mathematical_scores.get('risk_penalty', 0),
                thesis_probability=mathematical_scores.get('thesis_probability', 0),
                timing=mathematical_scores.get('timing', 0),
            )
            
            if not investable:
                logger.warning(f"LLM recommended {decision_type} but fails investability gate")
                decision['decision'] = 'WATCH'
                decision['validation_override'] = 'Failed investability gate'
        
        # If LLM recommends hold/trim/sell, verify reasons
        if decision_type in ['TRIM', 'SELL']:
            # Check if forward expected return justifies action
            forward_return = mathematical_scores.get('forward_expected_return', 0)
            
            if decision_type == 'SELL' and forward_return > 0.05:
                logger.warning(f"LLM recommended SELL but forward return {forward_return:.2%} is positive")
                decision['decision'] = 'HOLD'
                decision['validation_override'] = 'Forward return still positive'
        
        return decision
