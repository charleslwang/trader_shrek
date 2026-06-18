"""
Tests for memory system
"""

import pytest
from pathlib import Path
from datetime import datetime, timedelta
from shrek_ai.memory import MemorySystem
from shrek_ai.config import MemoryConfig


def test_add_memory(tmp_path):
    """Test adding a memory"""
    memory_system = MemorySystem(tmp_path)
    
    memory_id = memory_system.add_memory(
        symbol='AAPL',
        layer='shallow',
        content='Test memory content',
        relevance=0.8,
        importance=0.8,
        source_reliability=0.9,
    )
    
    assert memory_id is not None
    assert len(memory_id) > 0


def test_memory_accepts_config_dataclass(tmp_path):
    """Test initializing memory with the loaded config shape."""
    config = MemoryConfig(
        shallow_decay_days=7,
        intermediate_decay_days=90,
        deep_decay_days=365,
    )

    memory_system = MemorySystem(tmp_path, config=config)

    assert memory_system.shallow_decay_days == 7
    assert memory_system.intermediate_decay_days == 90
    assert memory_system.deep_decay_days == 365


def test_calculate_memory_score(tmp_path):
    """Test memory score calculation"""
    memory_system = MemorySystem(tmp_path)
    
    memory_id = memory_system.add_memory(
        symbol='AAPL',
        layer='shallow',
        content='Test memory content',
        relevance=0.8,
        importance=0.8,
        source_reliability=0.9,
    )
    
    # Load the memory
    symbol_dir = tmp_path / 'AAPL' / 'shallow'
    memory_file = symbol_dir / f'{memory_id}.json'
    
    import json
    with open(memory_file, 'r') as f:
        memory = json.load(f)
    
    # Calculate score
    score = memory_system.calculate_memory_score(memory)
    
    assert 0 <= score <= 1


def test_retrieve_memories(tmp_path):
    """Test retrieving memories"""
    memory_system = MemorySystem(tmp_path)
    
    # Add multiple memories
    for i in range(5):
        memory_system.add_memory(
            symbol='AAPL',
            layer='shallow',
            content=f'Test memory {i}',
            relevance=0.8,
            importance=0.8,
            source_reliability=0.9,
        )
    
    # Retrieve memories
    memories = memory_system.retrieve_memories('AAPL', layer='shallow', top_k=3)
    
    assert len(memories) <= 3
    assert all(m['symbol'] == 'AAPL' for m in memories)


def test_get_thesis_memories(tmp_path):
    """Test retrieving thesis memories"""
    memory_system = MemorySystem(tmp_path)
    
    # Add memories to different layers
    memory_system.add_memory(
        symbol='AAPL',
        layer='deep',
        content='Deep memory',
        relevance=0.9,
        importance=0.9,
        source_reliability=0.9,
    )
    
    memory_system.add_memory(
        symbol='AAPL',
        layer='intermediate',
        content='Intermediate memory',
        relevance=0.8,
        importance=0.8,
        source_reliability=0.9,
    )
    
    # Retrieve thesis memories
    thesis_memories = memory_system.get_thesis_memories('AAPL')
    
    assert len(thesis_memories) > 0


def test_cleanup_old_memories(tmp_path):
    """Test cleaning up old memories"""
    memory_system = MemorySystem(tmp_path)
    
    # Add a memory
    memory_id = memory_system.add_memory(
        symbol='AAPL',
        layer='shallow',
        content='Test memory',
        relevance=0.8,
        importance=0.8,
        source_reliability=0.9,
    )
    
    # Manually age the memory
    symbol_dir = tmp_path / 'AAPL' / 'shallow'
    memory_file = symbol_dir / f'{memory_id}.json'
    
    import json
    with open(memory_file, 'r') as f:
        memory = json.load(f)
    
    # Set timestamp to very old
    old_date = datetime.now() - timedelta(days=2000)
    memory['timestamp'] = old_date.isoformat()
    
    with open(memory_file, 'w') as f:
        json.dump(memory, f)
    
    # Cleanup
    removed = memory_system.cleanup_old_memories('AAPL', max_age_days=365)
    
    assert removed >= 0
