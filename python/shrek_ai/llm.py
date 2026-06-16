"""
LLM client for interacting with Ollama and other LLM providers
"""

from typing import Optional, Dict, Any
import requests
import json
from loguru import logger


class LLMClient:
    """Client for interacting with LLM providers"""
    
    def __init__(self, base_url: str, model: str):
        self.base_url = base_url
        self.model = model
    
    def generate(
        self,
        prompt: str,
        require_json: bool = True,
        temperature: float = 0.0,
        max_tokens: int = 2000,
    ) -> str:
        """
        Generate text from LLM.
        
        Args:
            prompt: Input prompt
            require_json: Whether to require JSON output
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
        
        Returns:
            Generated text
        """
        url = f"{self.base_url}/api/generate"
        
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }
        
        if require_json:
            payload["prompt"] = f"{prompt}\n\nYou must respond with valid JSON only."
        
        try:
            response = requests.post(url, json=payload, timeout=120)
            response.raise_for_status()
            
            result = response.json()
            return result.get("response", "")
        
        except requests.exceptions.RequestException as e:
            logger.error(f"LLM request failed: {e}")
            return ""
    
    def chat(
        self,
        messages: list[Dict[str, str]],
        require_json: bool = True,
        temperature: float = 0.0,
        max_tokens: int = 2000,
    ) -> str:
        """
        Generate text from LLM using chat interface.
        
        Args:
            messages: List of chat messages
            require_json: Whether to require JSON output
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
        
        Returns:
            Generated text
        """
        url = f"{self.base_url}/api/chat"
        
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }
        
        if require_json:
            payload["messages"][-1]["content"] += "\n\nYou must respond with valid JSON only."
        
        try:
            response = requests.post(url, json=payload, timeout=120)
            response.raise_for_status()
            
            result = response.json()
            return result.get("message", {}).get("content", "")
        
        except requests.exceptions.RequestException as e:
            logger.error(f"LLM chat request failed: {e}")
            return ""
    
    def check_connection(self) -> bool:
        """
        Check if LLM server is accessible.
        
        Returns:
            True if accessible, False otherwise
        """
        try:
            url = f"{self.base_url}/api/tags"
            response = requests.get(url, timeout=5)
            response.raise_for_status()
            return True
        except requests.exceptions.RequestException:
            return False
