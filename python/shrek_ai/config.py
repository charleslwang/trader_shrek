"""Configuration loading and validation for Shrek."""

from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings


class AccountConfig(BaseModel):
    name: str
    mode: str = "paper"
    expected_equity: float = 100.0


class SessionConfig(BaseModel):
    timezone: str = "America/New_York"
    regular_open: str = "09:30"
    observe_start: str = "09:30"
    observe_until: str = "10:00"
    active_start: str = "10:00"
    active_end: str = "15:30"
    flatten_start: str = "15:30"
    force_flat: str = "15:55"
    extended_hours: bool = False


class UniverseConfig(BaseModel):
    focus: str = "same_day_small_mid_volatility"
    watchlist_size: int = 50
    refresh_watchlist_minutes: int = 45

    require_active: bool = True
    require_tradable: bool = True
    require_fractionable: bool = True

    exclude_etfs: bool = True
    exclude_mega_caps: bool = True

    allowed_exchanges: list[str] = ["NYSE", "NASDAQ", "ARCA", "BATS"]

    price_min: float = 2.00
    price_max: float = 80.00

    min_relative_volume_after_open: float = 1.5
    min_current_5m_dollar_volume: float = 250000
    min_current_15m_dollar_volume: float = 750000
    min_intraday_range_bps: float = 150
    min_abs_return_since_open_bps: float = 40
    max_spread_bps: float = 25.0


class ScanConfig(BaseModel):
    interval_seconds: int = 60
    horizons_minutes: list[int] = [5, 10, 15, 30, 60]
    max_new_entries_per_minute: int = 2
    max_trades_per_day: int = 100
    max_open_positions: int = 20


class ModelConfig(BaseModel):
    type: str = "same_day_online_ensemble"
    update_online: bool = True
    min_observation_minutes_before_trading: int = 30
    min_samples_before_online_update: int = 50

    probability_entry_threshold_5m: float = 0.60
    probability_entry_threshold_10m: float = 0.58
    probability_entry_threshold_15m: float = 0.56
    probability_entry_threshold_30m: float = 0.55
    probability_entry_threshold_60m: float = 0.54

    probability_exit_threshold: float = 0.50
    min_expected_edge_after_cost_bps: float = 7.0

    ensemble: EnsembleConfig


class EnsembleConfig(BaseModel):
    logistic_weight: float = 0.40
    bucket_weight: float = 0.25
    knn_weight: float = 0.20
    transition_weight: float = 0.15
    adaptive_weights: bool = True


class ExecutionConfig(BaseModel):
    long_only: bool = True
    allow_shorts: bool = False
    allow_options: bool = False
    allow_market_entries: bool = False
    allow_extended_hours: bool = False

    entry_order_type: str = "limit"
    time_in_force: str = "day"
    entry_timeout_seconds: int = 15
    no_chase_after_cancel: bool = True
    max_signal_age_seconds: int = 60
    limit_price_offset_bps: float = 2.0

    min_position_notional: float = 1.00
    base_position_notional: float = 2.00
    max_position_notional: float = 3.00
    max_total_exposure: float = 60.00
    max_symbol_exposure: float = 3.00
    max_same_symbol_trades_per_day: int = 3


class RiskConfig(BaseModel):
    max_daily_loss: Optional[float] = None
    soft_daily_loss: Optional[float] = None
    stop_after_consecutive_losses: Optional[int] = None

    kill_switch_on_broker_error: bool = True
    kill_switch_on_reconcile_failure: bool = True
    reject_stale_signals: bool = True
    reject_wide_spreads: bool = True
    reject_duplicate_symbols: bool = True
    reject_after_flatten_start: bool = True


class ExitsConfig(BaseModel):
    adaptive_take_profit: bool = True
    adaptive_stop: bool = True
    default_take_profit_pct: float = 0.008
    default_stop_pct: float = 0.005
    min_take_profit_pct: float = 0.006
    max_take_profit_pct: float = 0.018
    min_stop_pct: float = 0.004
    max_stop_pct: float = 0.012
    max_hold_minutes_5m: int = 8
    max_hold_minutes_10m: int = 15
    max_hold_minutes_15m: int = 20
    max_hold_minutes_30m: int = 40
    max_hold_minutes_60m: int = 75
    force_flat: bool = True


class LLMConfig(BaseModel):
    enabled: bool = False
    intraday_direct_trading: bool = False
    postmarket_review: bool = True
    runtime: str = "ollama"
    model: str = "qwen3:8b"


class LoggingConfig(BaseModel):
    log_all_bars: bool = True
    log_all_features: bool = True
    log_all_predictions: bool = True
    log_all_signals: bool = True
    log_all_trade_intents: bool = True
    log_all_rejections: bool = True
    log_all_fills: bool = True
    log_shadow_baselines: bool = True


class ShrekConfig(BaseModel):
    account: AccountConfig
    session: SessionConfig
    universe: UniverseConfig
    scan: ScanConfig
    model: ModelConfig
    execution: ExecutionConfig
    risk: RiskConfig
    exits: ExitsConfig
    llm: LLMConfig
    logging: LoggingConfig


class EnvSettings(BaseSettings):
    alpaca_api_key: str
    alpaca_secret_key: str
    alpaca_trading_base_url: str = "https://paper-api.alpaca.markets"
    alpaca_data_base_url: str = "https://data.alpaca.markets"
    alpaca_data_feed: str = "iex"
    shrek_mode: str = "paper"
    shrek_config: str = "config/shrek.paper.yaml"
    rust_log: str = "info"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen3:8b"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Refuse live mode
        if self.shrek_mode == "live":
            raise ValueError("Live mode is not allowed. Use 'paper' or 'dry-run'.")


def load_config(config_path: Optional[str] = None) -> ShrekConfig:
    """Load YAML configuration file."""
    if config_path is None:
        env = EnvSettings()
        config_path = env.shrek_config

    config_file = Path(config_path)
    if not config_file.is_absolute() and not config_file.exists():
        project_root = Path(__file__).resolve().parent.parent.parent
        config_file = project_root / config_path

    if not config_file.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(config_file) as f:
        config_data = yaml.safe_load(f)

    return ShrekConfig(**config_data)


def get_env_settings() -> EnvSettings:
    """Load environment settings."""
    return EnvSettings()
