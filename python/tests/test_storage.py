"""
Tests for storage layer
"""

import pytest
from pathlib import Path
from datetime import datetime
from shrek_ai.storage import StorageManager


def test_storage_initialization(tmp_path):
    """Test storage manager initialization"""
    storage_manager = StorageManager(tmp_path)
    
    assert storage_manager.storage_dir == tmp_path
    assert storage_manager.db_path.exists()


def test_save_decision(tmp_path):
    """Test saving a decision"""
    storage_manager = StorageManager(tmp_path)
    
    decision = {
        'decision_id': 'test-001',
        'date': datetime.now().date().isoformat(),
        'symbol': 'AAPL',
        'current_price': 150.0,
        'v_bear': 120.0,
        'v_base': 150.0,
        'v_bull': 180.0,
        'p_bear': 0.30,
        'p_base': 0.50,
        'p_bull': 0.20,
        'expected_return': 0.20,
        'downside': 0.20,
        'upside_downside': 2.0,
        'thesis_probability': 0.70,
        'quality_score': 0.70,
        'piotroski_score': 0.70,
        'revision_score': 0.50,
        'timing_score': 0.50,
        'risk_penalty': 0.30,
        'shrek_score': 0.75,
        'decision': 'BUY_STARTER',
        'notional': 10000.0,
        'order_sent': False,
        'rust_accept': False,
        'rust_reject_reason': None,
        'source_docs': 'test',
        'memo_path': None,
    }
    
    storage_manager.save_decision(decision)
    
    # Retrieve and verify
    decisions = storage_manager.get_decisions(symbol='AAPL')
    assert len(decisions) == 1
    assert decisions.iloc[0]['decision_id'] == 'test-001'


def test_get_decisions(tmp_path):
    """Test retrieving decisions"""
    storage_manager = StorageManager(tmp_path)
    
    # Save multiple decisions
    for i in range(3):
        decision = {
            'decision_id': f'test-{i:03d}',
            'date': datetime.now().date().isoformat(),
            'symbol': 'AAPL',
            'current_price': 150.0,
            'v_bear': 120.0,
            'v_base': 150.0,
            'v_bull': 180.0,
            'p_bear': 0.30,
            'p_base': 0.50,
            'p_bull': 0.20,
            'expected_return': 0.20,
            'downside': 0.20,
            'upside_downside': 2.0,
            'thesis_probability': 0.70,
            'quality_score': 0.70,
            'piotroski_score': 0.70,
            'revision_score': 0.50,
            'timing_score': 0.50,
            'risk_penalty': 0.30,
            'shrek_score': 0.75,
            'decision': 'BUY_STARTER',
            'notional': 10000.0,
            'order_sent': False,
            'rust_accept': False,
            'rust_reject_reason': None,
            'source_docs': 'test',
            'memo_path': None,
        }
        storage_manager.save_decision(decision)
    
    # Retrieve
    decisions = storage_manager.get_decisions(symbol='AAPL')
    assert len(decisions) == 3


def test_save_feature(tmp_path):
    """Test saving a feature"""
    storage_manager = StorageManager(tmp_path)
    
    storage_manager.save_feature(
        feature_id='feature-001',
        date=datetime.now().date().isoformat(),
        symbol='AAPL',
        feature_name='revenue_growth',
        feature_value=0.15,
        layer='intermediate',
    )
    
    # Retrieve and verify
    features = storage_manager.get_features(symbol='AAPL', feature_name='revenue_growth')
    assert len(features) == 1
    assert features.iloc[0]['feature_value'] == 0.15


def test_export_to_parquet(tmp_path):
    """Test exporting to Parquet"""
    storage_manager = StorageManager(tmp_path)
    
    # Save a decision
    decision = {
        'decision_id': 'test-001',
        'date': datetime.now().date().isoformat(),
        'symbol': 'AAPL',
        'current_price': 150.0,
        'v_bear': 120.0,
        'v_base': 150.0,
        'v_bull': 180.0,
        'p_bear': 0.30,
        'p_base': 0.50,
        'p_bull': 0.20,
        'expected_return': 0.20,
        'downside': 0.20,
        'upside_downside': 2.0,
        'thesis_probability': 0.70,
        'quality_score': 0.70,
        'piotroski_score': 0.70,
        'revision_score': 0.50,
        'timing_score': 0.50,
        'risk_penalty': 0.30,
        'shrek_score': 0.75,
        'decision': 'BUY_STARTER',
        'notional': 10000.0,
        'order_sent': False,
        'rust_accept': False,
        'rust_reject_reason': None,
        'source_docs': 'test',
        'memo_path': None,
    }
    storage_manager.save_decision(decision)
    
    # Export
    output_path = tmp_path / 'decisions.parquet'
    result_path = storage_manager.export_to_parquet('decisions', output_path)
    
    assert result_path.exists()
