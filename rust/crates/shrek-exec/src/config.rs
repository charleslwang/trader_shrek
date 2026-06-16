//! Configuration for the execution daemon.

use anyhow::{Context, Result};
use serde::Deserialize;

#[derive(Debug, Clone, Deserialize)]
pub struct AccountConfig {
    pub name: String,
    pub mode: String,
    pub expected_equity: f64,
}

#[derive(Debug, Clone, Deserialize)]
pub struct SessionConfig {
    pub timezone: String,
    pub regular_open: String,
    pub observe_start: String,
    pub observe_until: String,
    pub active_start: String,
    pub active_end: String,
    pub flatten_start: String,
    pub force_flat: String,
    pub extended_hours: bool,
}

#[derive(Debug, Clone, Deserialize)]
pub struct ExecutionConfig {
    pub long_only: bool,
    pub allow_shorts: bool,
    pub allow_options: bool,
    pub allow_market_entries: bool,
    pub allow_extended_hours: bool,

    pub entry_order_type: String,
    pub time_in_force: String,
    pub entry_timeout_seconds: i64,
    pub no_chase_after_cancel: bool,
    pub max_signal_age_seconds: i64,
    pub limit_price_offset_bps: f64,

    pub min_position_notional: f64,
    pub base_position_notional: f64,
    pub max_position_notional: f64,
    pub max_total_exposure: f64,
    pub max_symbol_exposure: f64,
    pub max_same_symbol_trades_per_day: i64,
}

#[derive(Debug, Clone, Deserialize)]
pub struct RiskConfig {
    pub max_daily_loss: Option<f64>,
    pub soft_daily_loss: Option<f64>,
    pub stop_after_consecutive_losses: Option<i64>,

    pub kill_switch_on_broker_error: bool,
    pub kill_switch_on_reconcile_failure: bool,
    pub reject_stale_signals: bool,
    pub reject_wide_spreads: bool,
    pub reject_duplicate_symbols: bool,
    pub reject_after_flatten_start: bool,
}

#[derive(Debug, Clone, Deserialize)]
pub struct ScoringConfig {
    pub min_expected_edge_after_cost_bps: f64,
}

#[derive(Debug, Clone, Deserialize)]
pub struct ExecConfig {
    pub account: AccountConfig,
    pub session: SessionConfig,
    pub execution: ExecutionConfig,
    pub risk: RiskConfig,
    pub scoring: ScoringConfig,
}

/// Load the execution daemon config from a YAML file path.
pub fn load_config(path: &str) -> Result<ExecConfig> {
    let contents = std::fs::read_to_string(path)
        .with_context(|| format!("Failed to read config file: {}", path))?;
    let config: ExecConfig = serde_yaml::from_str(&contents)
        .with_context(|| format!("Failed to parse config file: {}", path))?;
    Ok(config)
}
