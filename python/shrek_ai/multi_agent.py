"""
Multi-agent debate system for Shrek
Two agents with opposing perspectives debate until consensus or max rounds
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from loguru import logger
from datetime import datetime
import json

from .llm import LLMClient
from .config import MultiAgentConfig, AgentConfig
from .decision_policy import normalize_decision_label


@dataclass
class DebateMessage:
    """A single message in the debate"""
    agent_name: str
    role: str
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    confidence: float = 0.0
    decision: Optional[Dict[str, Any]] = None


@dataclass
class DebateResult:
    """Result of a multi-agent debate"""
    consensus_reached: bool
    final_decision: Optional[Dict[str, Any]]
    consensus_score: float
    messages: List[DebateMessage]
    rounds: int
    reasoning: str


class MultiAgentDebater:
    """Orchestrates debate between two agents with opposing perspectives"""
    
    def __init__(self, config: MultiAgentConfig):
        self.config = config
        
        # Initialize agents with their respective runtimes and models
        self.agent_a = LLMClient(
            runtime=config.agent_1.runtime,
            model=config.agent_1.model,
            base_url=config.agent_1.base_url or self._get_default_base_url(config.agent_1.runtime),
            api_key_env=config.agent_1.api_key_env
        )
        self.agent_b = LLMClient(
            runtime=config.agent_2.runtime,
            model=config.agent_2.model,
            base_url=config.agent_2.base_url or self._get_default_base_url(config.agent_2.runtime),
            api_key_env=config.agent_2.api_key_env
        )
        
        # System prompts for each agent
        self.system_prompts = {
            config.agent_1.name: self._build_system_prompt(config.agent_1),
            config.agent_2.name: self._build_system_prompt(config.agent_2),
        }
    
    def _get_default_base_url(self, runtime: str) -> str:
        """Get default base URL for a runtime"""
        defaults = {
            "ollama": "http://localhost:11434",
            "openai": "https://api.openai.com/v1",
            "huggingface": "https://api-inference.huggingface.co/models",
        }
        return defaults.get(runtime, "http://localhost:11434")
    
    def _build_system_prompt(self, agent_config: AgentConfig) -> str:
        """Build system prompt for an agent based on their role and personality"""
        base_prompt = f"""You are {agent_config.name}, a financial analyst with the following perspective:
Role: {agent_config.role}
Personality: {agent_config.personality}

Your task is to analyze investment decisions from your unique perspective and engage in constructive debate with another analyst who has a different viewpoint.

Guidelines:
- Base your analysis on provided financial data, SEC filings, and market information
- Cite specific evidence to support your arguments
- Be willing to reconsider your position if presented with compelling evidence
- Focus on objective analysis rather than emotional arguments
- Provide clear reasoning for your recommendations
- Assign a confidence score (0.0-1.0) to your conclusions
"""
        return base_prompt
    
    def debate_decision(
        self,
        context: str,
        decision_type: str,
        additional_context: Optional[Dict[str, Any]] = None
    ) -> DebateResult:
        """
        Orchestrate a debate between agents to reach a decision
        
        Args:
            context: The context for the decision (company data, filings, etc.)
            decision_type: Type of decision (buy, sell, hold, rebalance, etc.)
            additional_context: Additional context specific to the decision
        
        Returns:
            DebateResult with consensus status and final decision
        """
        messages: List[DebateMessage] = []
        conversation_history: List[Dict[str, str]] = []
        
        # Initial prompt for both agents
        initial_prompt = self._build_initial_prompt(context, decision_type, additional_context)
        
        # Round 1: Get initial positions
        logger.info(f"Starting multi-agent debate for {decision_type}")
        
        agent_a_response = self._get_agent_response(
            self.config.agent_1.name,
            initial_prompt,
            conversation_history
        )
        messages.append(DebateMessage(
            agent_name=self.config.agent_1.name,
            role=self.config.agent_1.role,
            content=agent_a_response['reasoning'],
            confidence=agent_a_response.get('confidence', 0.5),
            decision=agent_a_response.get('decision')
        ))
        conversation_history.append({
            "role": "assistant",
            "name": self.config.agent_1.name,
            "content": agent_a_response['reasoning']
        })
        
        agent_b_response = self._get_agent_response(
            self.config.agent_2.name,
            initial_prompt,
            conversation_history
        )
        messages.append(DebateMessage(
            agent_name=self.config.agent_2.name,
            role=self.config.agent_2.role,
            content=agent_b_response['reasoning'],
            confidence=agent_b_response.get('confidence', 0.5),
            decision=agent_b_response.get('decision')
        ))
        conversation_history.append({
            "role": "assistant",
            "name": self.config.agent_2.name,
            "content": agent_b_response['reasoning']
        })
        
        # Check for initial consensus
        consensus_score = self._calculate_consensus_score(
            agent_a_response.get('decision'),
            agent_b_response.get('decision')
        )
        
        if consensus_score >= self.config.consensus_threshold:
            logger.info(f"Consensus reached in round 1: {consensus_score:.2f}")
            return DebateResult(
                consensus_reached=True,
                final_decision=self._merge_decisions(
                    agent_a_response.get('decision'),
                    agent_b_response.get('decision')
                ),
                consensus_score=consensus_score,
                messages=messages,
                rounds=1,
                reasoning="Consensus reached on initial positions"
            )
        
        # Subsequent rounds: Debate until consensus or max rounds
        for round_num in range(2, self.config.max_conversation_rounds + 1):
            logger.info(f"Debate round {round_num}")
            
            # Agent A responds to Agent B's position
            rebuttal_prompt = self._build_rebuttal_prompt(
                agent_b_response['reasoning'],
                agent_b_response.get('decision'),
                round_num
            )
            
            agent_a_response = self._get_agent_response(
                self.config.agent_1.name,
                rebuttal_prompt,
                conversation_history
            )
            messages.append(DebateMessage(
                agent_name=self.config.agent_1.name,
                role=self.config.agent_1.role,
                content=agent_a_response['reasoning'],
                confidence=agent_a_response.get('confidence', 0.5),
                decision=agent_a_response.get('decision')
            ))
            conversation_history.append({
                "role": "assistant",
                "name": self.config.agent_1.name,
                "content": agent_a_response['reasoning']
            })
            
            # Agent B responds to Agent A's rebuttal
            rebuttal_prompt = self._build_rebuttal_prompt(
                agent_a_response['reasoning'],
                agent_a_response.get('decision'),
                round_num
            )
            
            agent_b_response = self._get_agent_response(
                self.config.agent_2.name,
                rebuttal_prompt,
                conversation_history
            )
            messages.append(DebateMessage(
                agent_name=self.config.agent_2.name,
                role=self.config.agent_2.role,
                content=agent_b_response['reasoning'],
                confidence=agent_b_response.get('confidence', 0.5),
                decision=agent_b_response.get('decision')
            ))
            conversation_history.append({
                "role": "assistant",
                "name": self.config.agent_2.name,
                "content": agent_b_response['reasoning']
            })
            
            # Check for consensus
            consensus_score = self._calculate_consensus_score(
                agent_a_response.get('decision'),
                agent_b_response.get('decision')
            )
            
            if consensus_score >= self.config.consensus_threshold:
                logger.info(f"Consensus reached in round {round_num}: {consensus_score:.2f}")
                return DebateResult(
                    consensus_reached=True,
                    final_decision=self._merge_decisions(
                        agent_a_response.get('decision'),
                        agent_b_response.get('decision')
                    ),
                    consensus_score=consensus_score,
                    messages=messages,
                    rounds=round_num,
                    reasoning=f"Consensus reached after {round_num} rounds of debate"
                )
        
        # Max rounds reached without consensus
        logger.warning(f"No consensus reached after {self.config.max_conversation_rounds} rounds")
        return DebateResult(
            consensus_reached=False,
            final_decision=self._merge_decisions(
                agent_a_response.get('decision'),
                agent_b_response.get('decision'),
                force_merge=True
            ),
            consensus_score=consensus_score,
            messages=messages,
            rounds=self.config.max_conversation_rounds,
            reasoning=f"No consensus reached after {self.config.max_conversation_rounds} rounds. Using weighted decision."
        )
    
    def _build_initial_prompt(
        self,
        context: str,
        decision_type: str,
        additional_context: Optional[Dict[str, Any]]
    ) -> str:
        """Build initial prompt for the debate"""
        prompt = f"""Analyze the following investment opportunity and provide your recommendation:

Decision Type: {decision_type}

Context:
{context}

"""
        if additional_context:
            prompt += f"\nAdditional Information:\n{json.dumps(additional_context, indent=2)}\n"
        
        prompt += """
Please provide:
1. Your analysis of the opportunity
2. Your recommendation using exactly one action from:
   AVOID, WATCH, HOLD, BUY_STARTER, ADD, CONVICTION_BUY, TRIM, SELL
3. Your confidence level (0.0-1.0)
4. Key factors supporting your decision
5. Key risks or concerns

Respond in JSON format with the following structure:
{
    "reasoning": "detailed analysis",
    "decision": {
        "action": "AVOID/WATCH/HOLD/BUY_STARTER/ADD/CONVICTION_BUY/TRIM/SELL",
        "position_size": "recommended size if applicable",
        "confidence": 0.0-1.0,
        "key_factors": ["factor1", "factor2"],
        "risks": ["risk1", "risk2"]
    },
    "confidence": 0.0-1.0
}
"""
        return prompt
    
    def _build_rebuttal_prompt(
        self,
        opponent_reasoning: str,
        opponent_decision: Dict[str, Any],
        round_num: int
    ) -> str:
        """Build rebuttal prompt for responding to opponent's argument"""
        prompt = f"""Your colleague has provided the following analysis (Round {round_num}):

Opponent's Analysis:
{opponent_reasoning}

Opponent's Decision:
{json.dumps(opponent_decision, indent=2)}

Please respond with:
1. Points where you agree with your colleague
2. Points where you disagree and why
3. Additional evidence or reasoning to support your position
4. Whether this changes your recommendation
5. Your updated confidence level

If you find your colleague's arguments compelling, be willing to adjust your position. If you maintain your position, provide strong evidence.

Respond in JSON format with the same structure as before.
"""
        return prompt
    
    def _get_agent_response(
        self,
        agent_name: str,
        prompt: str,
        conversation_history: List[Dict[str, str]]
    ) -> Dict[str, Any]:
        """Get response from a specific agent"""
        messages = [
            {"role": "system", "content": self.system_prompts[agent_name]}
        ]
        
        # Add conversation history
        for msg in conversation_history:
            messages.append(msg)
        
        # Add current prompt
        messages.append({"role": "user", "content": prompt})
        
        # Get response
        if agent_name == self.config.agent_1.name:
            response = self.agent_a.chat(messages, require_json=True)
        else:
            response = self.agent_b.chat(messages, require_json=True)
        
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            logger.error(f"Failed to parse JSON response from {agent_name}")
            return {
                "reasoning": response,
                "decision": None,
                "confidence": 0.0
            }
    
    def _calculate_consensus_score(
        self,
        decision_a: Optional[Dict[str, Any]],
        decision_b: Optional[Dict[str, Any]]
    ) -> float:
        """Calculate consensus score between two decisions"""
        if not decision_a or not decision_b:
            return 0.0
        
        # Check if actions match
        action_a = normalize_decision_label(decision_a.get('action', ''))
        action_b = normalize_decision_label(decision_b.get('action', ''))
        
        if action_a != action_b:
            return 0.0
        
        # If actions match, calculate confidence-weighted consensus
        confidence_a = decision_a.get('confidence', 0.0)
        confidence_b = decision_b.get('confidence', 0.0)
        
        # Average confidence
        avg_confidence = (confidence_a + confidence_b) / 2.0
        
        # Boost score if both have high confidence
        if confidence_a > 0.7 and confidence_b > 0.7:
            avg_confidence *= 1.1
        
        return min(avg_confidence, 1.0)
    
    def _merge_decisions(
        self,
        decision_a: Optional[Dict[str, Any]],
        decision_b: Optional[Dict[str, Any]],
        force_merge: bool = False
    ) -> Dict[str, Any]:
        """Merge two decisions into a final decision"""
        if not decision_a and not decision_b:
            return {"action": "hold", "confidence": 0.0}
        
        if not decision_a:
            return decision_b
        
        if not decision_b:
            return decision_a
        
        # If actions match, use the more confident one
        if normalize_decision_label(decision_a.get('action')) == normalize_decision_label(decision_b.get('action')):
            if decision_a.get('confidence', 0) >= decision_b.get('confidence', 0):
                return decision_a
            else:
                return decision_b
        
        # If actions differ and not forcing merge, default to hold
        if not force_merge:
            return {
                "action": "hold",
                "confidence": 0.0,
                "reasoning": "No consensus - defaulting to hold"
            }
        
        # Force merge: use weighted average of confidences
        confidence_a = decision_a.get('confidence', 0.0)
        confidence_b = decision_b.get('confidence', 0.0)
        
        if confidence_a > confidence_b:
            return {
                **decision_a,
                "confidence": confidence_a * 0.7,  # Discount confidence when forcing
                "reasoning": f"Selected {decision_a.get('action')} with higher confidence ({confidence_a:.2f} vs {confidence_b:.2f})"
            }
        else:
            return {
                **decision_b,
                "confidence": confidence_b * 0.7,
                "reasoning": f"Selected {decision_b.get('action')} with higher confidence ({confidence_b:.2f} vs {confidence_a:.2f})"
            }
    
    def log_debate(self, result: DebateResult, decision_type: str, symbol: Optional[str] = None) -> None:
        """Log debate results for transparency and analysis"""
        if not self.config.log_debates:
            return
        
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "decision_type": decision_type,
            "symbol": symbol,
            "consensus_reached": result.consensus_reached,
            "consensus_score": result.consensus_score,
            "rounds": result.rounds,
            "final_decision": result.final_decision,
            "reasoning": result.reasoning,
            "messages": [
                {
                    "agent": msg.agent_name,
                    "role": msg.role,
                    "content": msg.content,
                    "confidence": msg.confidence,
                    "timestamp": msg.timestamp.isoformat()
                }
                for msg in result.messages
            ]
        }
        
        # Log to file
        log_file = "data/debates.jsonl"
        with open(log_file, 'a') as f:
            f.write(json.dumps(log_entry) + '\n')
        
        logger.info(f"Debate logged to {log_file}")
