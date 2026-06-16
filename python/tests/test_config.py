"""
Tests for configuration management
"""

import os
import pytest
from pathlib import Path
from shrek_ai.config import load_config, load_env, AccountConfig, SessionConfig


def test_load_env():
    """Test environment variable loading"""
    # Set test environment variables
    os.environ['SHREK_MODE'] = 'paper'
    os.environ['ALPACA_API_KEY'] = 'test_key'
    os.environ['ALPACA_SECRET_KEY'] = 'test_secret'
    os.environ['ALPACA_BASE_URL'] = 'https://paper-api.alpaca.markets'
    
    env = load_env()
    
    assert env['SHREK_MODE'] == 'paper'
    assert env['ALPACA_API_KEY'] == 'test_key'
    assert env['ALPACA_SECRET_KEY'] == 'test_secret'


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
    
    assert config.account.initial_cash > 0
    assert config.account.max_cash_reserve_pct >= 0
    assert config.account.max_cash_reserve_pct <= 1


def test_session_config():
    """Test session configuration"""
    config = load_config()
    
    assert config.session.timezone is not None
    assert config.session.market_open_time is not None
    assert config.session.market_close_time is not None
