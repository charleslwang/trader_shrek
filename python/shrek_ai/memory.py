"""
Memory system with layered decay for company information
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from pathlib import Path
import json
import math
from loguru import logger


class MemorySystem:
    """Layered memory system for company information"""
    
    def __init__(self, storage_dir: Path, config: Optional[Dict[str, int]] = None):
        self.storage_dir = storage_dir
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        
        if config is None:
            config = {
                'shallow_decay_days': 14,
                'intermediate_decay_days': 120,
                'deep_decay_days': 1095,
            }
        
        self.shallow_decay_days = config['shallow_decay_days']
        self.intermediate_decay_days = config['intermediate_decay_days']
        self.deep_decay_days = config['deep_decay_days']
    
    def add_memory(
        self,
        symbol: str,
        layer: str,
        content: str,
        relevance: float = 0.8,
        importance: float = 0.8,
        source_reliability: float = 0.9,
        source_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Add a memory to the system.
        
        Args:
            symbol: Stock symbol
            layer: Memory layer (shallow, intermediate, deep)
            content: Memory content
            relevance: Relevance score (0 to 1)
            importance: Importance score (0 to 1)
            source_reliability: Source reliability (0 to 1)
            source_id: Source identifier
            metadata: Optional metadata
        
        Returns:
            Memory ID
        """
        import uuid
        
        memory_id = str(uuid.uuid4())
        timestamp = datetime.now()
        
        memory = {
            'id': memory_id,
            'symbol': symbol,
            'layer': layer,
            'content': content,
            'relevance': relevance,
            'importance': importance,
            'source_reliability': source_reliability,
            'source_id': source_id,
            'timestamp': timestamp.isoformat(),
            'metadata': metadata or {},
        }
        
        # Save to layer-specific storage
        layer_dir = self.storage_dir / symbol / layer
        layer_dir.mkdir(parents=True, exist_ok=True)
        
        filepath = layer_dir / f"{memory_id}.json"
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(memory, f, indent=2, default=str)
        
        logger.debug(f"Added memory {memory_id} to {layer} layer for {symbol}")
        return memory_id
    
    def calculate_memory_score(
        self,
        memory: Dict[str, Any],
        current_time: Optional[datetime] = None,
    ) -> float:
        """
        Calculate memory score based on relevance, importance, recency, and source reliability.
        
        Args:
            memory: Memory data
            current_time: Current time (defaults to now)
        
        Returns:
            Memory score (0 to 1)
        """
        if current_time is None:
            current_time = datetime.now()
        
        # Get decay horizon for layer
        layer = memory['layer']
        if layer == 'shallow':
            decay_days = self.shallow_decay_days
        elif layer == 'intermediate':
            decay_days = self.intermediate_decay_days
        elif layer == 'deep':
            decay_days = self.deep_decay_days
        else:
            decay_days = 365
        
        # Calculate recency score
        timestamp = datetime.fromisoformat(memory['timestamp'])
        age_days = (current_time - timestamp).days
        recency = math.exp(-age_days / decay_days)
        
        # Calculate weighted score
        score = (
            0.40 * memory['relevance'] +
            0.30 * memory['importance'] +
            0.20 * recency +
            0.10 * memory['source_reliability']
        )
        
        return score
    
    def retrieve_memories(
        self,
        symbol: str,
        layer: Optional[str] = None,
        top_k: int = 10,
        min_score: float = 0.3,
        current_time: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve top memories for a symbol.
        
        Args:
            symbol: Stock symbol
            layer: Specific layer to retrieve (None for all layers)
            top_k: Number of memories to retrieve
            min_score: Minimum score threshold
            current_time: Current time
        
        Returns:
            List of memories sorted by score
        """
        memories = []
        
        # Determine which layers to search
        if layer:
            layers = [layer]
        else:
            layers = ['shallow', 'intermediate', 'deep']
        
        # Load memories from each layer
        for layer_name in layers:
            layer_dir = self.storage_dir / symbol / layer_name
            
            if not layer_dir.exists():
                continue
            
            for memory_file in layer_dir.glob('*.json'):
                with open(memory_file, 'r', encoding='utf-8') as f:
                    memory = json.load(f)
                
                # Calculate score
                score = self.calculate_memory_score(memory, current_time)
                
                if score >= min_score:
                    memory['score'] = score
                    memories.append(memory)
        
        # Sort by score descending
        memories.sort(key=lambda m: m['score'], reverse=True)
        
        # Return top k
        return memories[:top_k]
    
    def get_thesis_memories(
        self,
        symbol: str,
        current_time: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get memories relevant to investment thesis.
        
        Args:
            symbol: Stock symbol
            current_time: Current time
        
        Returns:
            List of thesis-relevant memories
        """
        # Prioritize deep and intermediate layers for thesis
        deep_memories = self.retrieve_memories(
            symbol, layer='deep', top_k=5, current_time=current_time
        )
        intermediate_memories = self.retrieve_memories(
            symbol, layer='intermediate', top_k=5, current_time=current_time
        )
        
        # Combine and deduplicate
        all_memories = deep_memories + intermediate_memories
        seen_ids = set()
        unique_memories = []
        
        for memory in all_memories:
            if memory['id'] not in seen_ids:
                seen_ids.add(memory['id'])
                unique_memories.append(memory)
        
        return unique_memories
    
    def cleanup_old_memories(
        self,
        symbol: str,
        max_age_days: Optional[int] = None,
    ) -> int:
        """
        Clean up old memories beyond age threshold.
        
        Args:
            symbol: Stock symbol
            max_age_days: Maximum age in days (defaults to deep decay days)
        
        Returns:
            Number of memories removed
        """
        if max_age_days is None:
            max_age_days = self.deep_decay_days
        
        removed = 0
        cutoff_date = datetime.now() - timedelta(days=max_age_days)
        
        for layer in ['shallow', 'intermediate', 'deep']:
            layer_dir = self.storage_dir / symbol / layer
            
            if not layer_dir.exists():
                continue
            
            for memory_file in layer_dir.glob('*.json'):
                with open(memory_file, 'r', encoding='utf-8') as f:
                    memory = json.load(f)
                
                timestamp = datetime.fromisoformat(memory['timestamp'])
                
                if timestamp < cutoff_date:
                    memory_file.unlink()
                    removed += 1
        
        logger.info(f"Cleaned up {removed} old memories for {symbol}")
        return removed
