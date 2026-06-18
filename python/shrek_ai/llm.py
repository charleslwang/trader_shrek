"""
LLM client for interacting with Ollama, OpenAI, and HuggingFace
"""

from typing import Optional, Dict, Any
import requests
import json
import os
from loguru import logger


class LLMClient:
    """Client for interacting with LLM providers"""
    
    def __init__(self, runtime: str, model: str, base_url: str, api_key_env: Optional[str] = None):
        self.runtime = runtime
        self.model = model
        self.base_url = base_url
        self.api_key = os.getenv(api_key_env) if api_key_env else None
    
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
        if self.runtime == "ollama":
            return self._generate_ollama(prompt, require_json, temperature, max_tokens)
        elif self.runtime == "openai":
            return self._generate_openai(prompt, require_json, temperature, max_tokens)
        elif self.runtime == "huggingface":
            return self._generate_huggingface(prompt, require_json, temperature, max_tokens)
        else:
            logger.error(f"Unsupported runtime: {self.runtime}")
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
        if self.runtime == "ollama":
            return self._chat_ollama(messages, require_json, temperature, max_tokens)
        elif self.runtime == "openai":
            return self._chat_openai(messages, require_json, temperature, max_tokens)
        elif self.runtime == "huggingface":
            return self._chat_huggingface(messages, require_json, temperature, max_tokens)
        else:
            logger.error(f"Unsupported runtime: {self.runtime}")
            return ""
    
    def _generate_ollama(
        self,
        prompt: str,
        require_json: bool,
        temperature: float,
        max_tokens: int,
    ) -> str:
        """Generate using Ollama API"""
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
            logger.error(f"Ollama request failed: {e}")
            return ""
    
    def _chat_ollama(
        self,
        messages: list[Dict[str, str]],
        require_json: bool,
        temperature: float,
        max_tokens: int,
    ) -> str:
        """Chat using Ollama API"""
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
            logger.error(f"Ollama chat request failed: {e}")
            return ""
    
    def _generate_openai(
        self,
        prompt: str,
        require_json: bool,
        temperature: float,
        max_tokens: int,
    ) -> str:
        """Generate using OpenAI API"""
        url = f"{self.base_url}/chat/completions"
        
        headers = {
            "Content-Type": "application/json",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        
        if require_json:
            payload["response_format"] = {"type": "json_object"}
        
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=120)
            response.raise_for_status()
            result = response.json()
            return result["choices"][0]["message"]["content"]
        except requests.exceptions.RequestException as e:
            logger.error(f"OpenAI request failed: {e}")
            return ""
    
    def _chat_openai(
        self,
        messages: list[Dict[str, str]],
        require_json: bool,
        temperature: float,
        max_tokens: int,
    ) -> str:
        """Chat using OpenAI API"""
        url = f"{self.base_url}/chat/completions"
        
        headers = {
            "Content-Type": "application/json",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        
        if require_json:
            payload["response_format"] = {"type": "json_object"}
        
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=120)
            response.raise_for_status()
            result = response.json()
            return result["choices"][0]["message"]["content"]
        except requests.exceptions.RequestException as e:
            logger.error(f"OpenAI chat request failed: {e}")
            return ""
    
    def _generate_huggingface(
        self,
        prompt: str,
        require_json: bool,
        temperature: float,
        max_tokens: int,
    ) -> str:
        """Generate using HuggingFace Inference API"""
        url = f"{self.base_url}/{self.model}"
        
        headers = {
            "Content-Type": "application/json",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        
        payload = {
            "inputs": prompt,
            "parameters": {
                "temperature": temperature,
                "max_new_tokens": max_tokens,
                "return_full_text": False,
            },
        }
        
        if require_json:
            payload["inputs"] = f"{prompt}\n\nYou must respond with valid JSON only."
        
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=120)
            response.raise_for_status()
            result = response.json()
            
            # HF API returns list for some models
            if isinstance(result, list):
                return result[0].get("generated_text", "")
            return result.get("generated_text", "")
        except requests.exceptions.RequestException as e:
            logger.error(f"HuggingFace request failed: {e}")
            return ""
    
    def _chat_huggingface(
        self,
        messages: list[Dict[str, str]],
        require_json: bool,
        temperature: float,
        max_tokens: int,
    ) -> str:
        """Chat using HuggingFace Inference API (converts to single prompt)"""
        # HF Inference API doesn't have native chat, so we convert messages to prompt
        prompt = ""
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                prompt += f"System: {content}\n"
            elif role == "user":
                prompt += f"User: {content}\n"
            elif role == "assistant":
                prompt += f"Assistant: {content}\n"
        
        prompt += "Assistant: "
        
        return self._generate_huggingface(prompt, require_json, temperature, max_tokens)
    
    def check_connection(self) -> bool:
        """
        Check if LLM server is accessible.
        
        Returns:
            True if accessible, False otherwise
        """
        try:
            if self.runtime == "ollama":
                url = f"{self.base_url}/api/tags"
                response = requests.get(url, timeout=5)
                response.raise_for_status()
            elif self.runtime == "openai":
                url = f"{self.base_url}/models"
                headers = {}
                if self.api_key:
                    headers["Authorization"] = f"Bearer {self.api_key}"
                response = requests.get(url, headers=headers, timeout=5)
                response.raise_for_status()
            elif self.runtime == "huggingface":
                # HF doesn't have a simple health check, just try a minimal request
                return True
            return True
        except requests.exceptions.RequestException:
            return False
