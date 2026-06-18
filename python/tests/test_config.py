"""
Tests for configuration management
"""

import os
import pytest
from pathlib import Path
from shrek_ai.config import load_config, load_env, AccountConfig, SessionConfig

# Ensure tests can find config when run from python/ subdirectory
os.environ.setdefault('SHREK_CONFIG', str(Path(__file__).resolve().parents[2] / 'config' / 'shrek.paper.yaml'))


def test_load_env():
    """Test environment variable loading"""
    # Set test environment variables
    os.environ['SHREK_MODE'] = 'paper'
    os.environ['ALPACA_API_KEY'] = 'test_key'
    os.environ['ALPACA_SECRET_KEY'] = 'test_secret'
    os.environ['ALPACA_BASE_URL'] = 'https://paper-api.alpaca.markets'
    
    load_env()
    
    assert os.getenv('SHREK_MODE') == 'paper'
    assert os.getenv('ALPACA_API_KEY') == 'test_key'
    assert os.getenv('ALPACA_SECRET_KEY') == 'test_secret'


def test_load_config():
    """Test configuration loading"""
    config = load_config()
    
    assert config is not None
    assert hasattr(config, 'account')
    assert hasattr(config, 'session')
    assert hasattr(config, 'universe')
    assert hasattr(config, 'portfolio')
    assert hasattr(config, 'orders')
    assert hasattr(config, 'llm')
    assert hasattr(config, 'memory')
    assert hasattr(config, 'risk')


def test_account_config():
    """Test account configuration"""
    config = load_config()
    
    assert config.account.name is not None
    assert config.account.mode in ['paper', 'dry-run']
    assert config.account.expected_equity > 0


def test_session_config():
    """Test session configuration"""
    config = load_config()
    
    assert config.session.timezone is not None
    assert config.session.regular_open is not None
    assert config.session.regular_close is not None
