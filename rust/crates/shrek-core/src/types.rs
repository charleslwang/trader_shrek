//! Core types for the Shrek trading system.

use chrono::{DateTime, Utc};
use rust_decimal::prelude::*;
use serde::{Deserialize, Serialize};
use uuid::Uuid;

use crate::money::Bps;

/// Stock symbol (e.g., "AAPL")
pub type Symbol = String;

/// Unique signal identifier
pub type SignalId = Uuid;

/// Execution mode
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum ExecutionMode {
    DryRun,
    Paper,
}

/// Kill switch state
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum KillSwitchState {
    Off,
    On,
}

/// Trade intent sent from Python to Rust
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TradeIntent {
    pub signal_id: SignalId,
    pub timestamp: DateTime<Utc>,
    pub symbol: Symbol,
    pub side: String,  // Only "buy" allowed
    pub notional: Decimal,
    pub limit_price: Decimal,
    pub horizon_minutes: i32,
    pub p_up: f64,
    pub expected_edge_bps: Bps,
    pub spread_bps: Bps,
    pub model_version: String,
    pub feature_snapshot_id: Uuid,
    pub max_hold_minutes: i32,
    pub stop_pct: Decimal,
    pub take_profit_pct: Decimal,
    pub reason: String,
}

/// Risk decision from Rust execution daemon
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RiskDecision {
    pub signal_id: SignalId,
    pub accepted: bool,
    pub reject_reason: Option<String>,
    pub timestamp: DateTime<Utc>,
}

/// Order state
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum OrderState {
    Pending,
    Submitted,
    PartiallyFilled,
    Filled,
    Cancelled,
    Rejected,
    Expired,
}

/// Position state
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PositionState {
    pub symbol: Symbol,
    pub quantity: Decimal,
    pub entry_price: Decimal,
    pub current_price: Decimal,
    pub unrealized_pnl: Decimal,
    pub entry_time: DateTime<Utc>,
    pub max_hold_minutes: i32,
    pub stop_price: Option<Decimal>,
    pub take_profit_price: Option<Decimal>,
}

/// Fill event
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FillEvent {
    pub fill_id: Uuid,
    pub signal_id: SignalId,
    pub symbol: Symbol,
    pub side: String,
    pub quantity: Decimal,
    pub fill_price: Decimal,
    pub timestamp: DateTime<Utc>,
}

/// Account snapshot
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AccountSnapshot {
    pub timestamp: DateTime<Utc>,
    pub equity: Decimal,
    pub cash: Decimal,
    pub long_market_value: Decimal,
    pub open_positions: i32,
}
