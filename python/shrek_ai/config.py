"""
Configuration management for Shrek
"""

import os
from pathlib import Path
from typing import Optional
import yaml
from dotenv import load_dotenv
from dataclasses import dataclass


@dataclass
class AccountConfig:
    name: str
    mode: str
    expected_equity: float


@dataclass
class SessionConfig:
    timezone: str
    regular_open: str
    regular_close: str
    place_orders_only_during_market_hours: bool
    no_extended_hours: bool


@dataclass
class UniverseConfig:
    asset_class: str
    require_active: bool
    require_tradable: bool
    require_fractionable: bool
    allow_etfs: bool
    allow_options: bool
    allow_shorts: bool
    min_price: float
    max_price: float
    min_market_cap: int
    max_positions: int
    candidate_limit_per_day: int


@dataclass
class PortfolioConfig:
    target_cash_reserve_pct: float
    max_single_position_pct: float
    starter_position_pct: float
    normal_position_pct: float
    max_new_buys_per_day: int
    max_sells_per_day: int
    rebalance_frequency_days: int


@dataclass
class EntryThresholds:
    min_shrek_score: float
    min_expected_return_12m: float
    min_upside_downside_ratio: float
    min_quality_score: float
    max_risk_penalty: float
    min_thesis_probability: float
    min_timing_score: float


@dataclass
class ExitThresholds:
    trim_forward_return_below: float
    sell_forward_return_below: float
    sell_thesis_probability_below: float
    review_thesis_probability_below: float
    trim_upside_downside_below: float
    sell_shrek_score_below: float
    sell_risk_penalty_above: float
    activate_trailing_after_gain: float


@dataclass
class OrdersConfig:
    default_order_type: str
    time_in_force: str
    limit_buy_discount_bps: int
    limit_sell_premium_bps: int
    order_timeout_minutes: int
    allow_market_orders: bool


@dataclass
class LLMConfig:
    enabled: bool
    runtime: str
    model: str
    api_key_env: Optional[str] = None
    base_url: Optional[str] = None
    require_json: bool = True
    require_source_citations: bool = True
    no_unsupported_claims: bool = True
    max_context_chunks: int = 12


@dataclass
class AgentConfig:
    name: str
    runtime: str
    model: str
    api_key_env: Optional[str] = None
    base_url: Optional[str] = None
    role: str = ""
    personality: str = ""


@dataclass
class MultiAgentConfig:
    enabled: bool
    max_conversation_rounds: int
    consensus_threshold: float
    log_debates: bool
    agent_1: AgentConfig
    agent_2: AgentConfig


@dataclass
class MemoryConfig:
    shallow_decay_days: int
    intermediate_decay_days: int
    deep_decay_days: int


@dataclass
class RiskConfig:
    no_daily_stop_loss: bool
    kill_switch_on_reconcile_failure: bool
    reject_if_market_closed: bool
    reject_if_asset_not_fractionable: bool
    reject_if_not_paper: bool


@dataclass
class Config:
    account: AccountConfig
    session: SessionConfig
    universe: UniverseConfig
    portfolio: PortfolioConfig
    entry_thresholds: EntryThresholds
    speculative_entry_thresholds: EntryThresholds
    exit_thresholds: ExitThresholds
    orders: OrdersConfig
    llm: LLMConfig
    multi_agent: Optional[MultiAgentConfig]
    memory: MemoryConfig
    risk: RiskConfig


def load_env() -> None:
    """Load environment variables from .env file"""
    load_dotenv()


def get_env(key: str, default: Optional[str] = None) -> str:
    """Get environment variable with optional default"""
    value = os.getenv(key, default)
    if value is None:
        raise ValueError(f"Environment variable {key} not set and no default provided")
    return value


def get_config_path() -> Path:
    """Get path to config file from environment or default"""
    config_path = os.getenv("SHREK_CONFIG", "config/shrek.paper.yaml")
    return Path(config_path)


def load_config(config_path: Optional[Path] = None) -> Config:
    """Load configuration from YAML file"""
    if config_path is None:
        config_path = get_config_path()
    
    with open(config_path, 'r') as f:
        config_dict = yaml.safe_load(f)
    
    # Handle optional multi_agent config
    multi_agent_config = None
    if 'multi_agent' in config_dict and config_dict['multi_agent'].get('enabled', False):
        multi_agent_config = MultiAgentConfig(
            enabled=config_dict['multi_agent']['enabled'],
            max_conversation_rounds=config_dict['multi_agent']['max_conversation_rounds'],
            consensus_threshold=config_dict['multi_agent']['consensus_threshold'],
            log_debates=config_dict['multi_agent']['log_debates'],
            agent_1=AgentConfig(**config_dict['multi_agent']['agent_1']),
            agent_2=AgentConfig(**config_dict['multi_agent']['agent_2']),
        )
    
    return Config(
        account=AccountConfig(**config_dict['account']),
        session=SessionConfig(**config_dict['session']),
        universe=UniverseConfig(**config_dict['universe']),
        portfolio=PortfolioConfig(**config_dict['portfolio']),
        entry_thresholds=EntryThresholds(**config_dict['entry_thresholds']),
        speculative_entry_thresholds=EntryThresholds(**config_dict['speculative_entry_thresholds']),
        exit_thresholds=ExitThresholds(**config_dict['exit_thresholds']),
        orders=OrdersConfig(**config_dict['orders']),
        llm=LLMConfig(**config_dict['llm']),
        multi_agent=multi_agent_config,
        memory=MemoryConfig(**config_dict['memory']),
        risk=RiskConfig(**config_dict['risk']),
    )


def get_alpaca_config() -> dict:
    """Get Alpaca API configuration from environment"""
    return {
        'api_key': get_env('ALPACA_API_KEY'),
        'secret_key': get_env('ALPACA_SECRET_KEY'),
        'base_url': get_env('ALPACA_TRADING_BASE_URL', 'https://paper-api.alpaca.markets'),
        'data_base_url': get_env('ALPACA_DATA_BASE_URL', 'https://data.alpaca.markets'),
        'data_feed': get_env('ALPACA_DATA_FEED', 'iex'),
    }


def get_llm_config() -> dict:
    """Get LLM configuration from environment"""
    return {
        'runtime': get_env('LLM_RUNTIME', 'ollama'),
        'base_url': get_env('OLLAMA_BASE_URL', 'http://localhost:11434'),
        'model': get_env('OLLAMA_MODEL', 'qwen3:8b'),
    }


def get_sec_config() -> dict:
    """Get SEC EDGAR configuration from environment"""
    return {
        'user_agent': get_env('SEC_USER_AGENT'),
    }


def get_shrek_mode() -> str:
    """Get Shrek mode from environment"""
    mode = get_env('SHREK_MODE', 'paper')
    if mode == 'live':
        raise ValueError("Live mode is explicitly disabled")
    return mode
