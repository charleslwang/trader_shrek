use chrono::{DateTime, Utc};
use rust_decimal::Decimal;
use serde::{Deserialize, Serialize};
use uuid::Uuid;

/// Trading mode
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum TradingMode {
    DryRun,
    Paper,
    // Live is explicitly disabled - will cause error if attempted
}

/// Order side
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum Side {
    Buy,
    Sell,
}

/// Order type
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum OrderType {
    Limit,
    Market,
}

/// Time in force
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum TimeInForce {
    Day,
    Gtc,
    Ioc,
    Fok,
}

/// Order status
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum OrderStatus {
    New,
    PartiallyFilled,
    Filled,
    Cancelled,
    Expired,
    Rejected,
}

/// Asset class
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum AssetClass {
    UsEquity,
    Crypto,
}

/// Order proposal from Python
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct OrderProposal {
    pub decision_id: Uuid,
    pub symbol: String,
    pub side: Side,
    pub notional: Decimal,
    pub order_type: OrderType,
    pub limit_price: Option<Decimal>,
    pub time_in_force: TimeInForce,
    pub reason: String,
    pub source_decision_path: String,
}

/// Order rejection reason
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct OrderRejection {
    pub decision_id: Uuid,
    pub reason: String,
    pub timestamp: DateTime<Utc>,
}

/// Order event for logging
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct OrderEvent {
    pub id: Uuid,
    pub decision_id: Uuid,
    pub client_order_id: String,
    pub symbol: String,
    pub side: Side,
    pub order_type: OrderType,
    pub limit_price: Option<Decimal>,
    pub quantity: Decimal,
    pub status: OrderStatus,
    pub filled_quantity: Decimal,
    pub filled_price: Option<Decimal>,
    pub timestamp: DateTime<Utc>,
}

/// Position snapshot
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Position {
    pub symbol: String,
    pub quantity: Decimal,
    pub avg_entry_price: Decimal,
    pub current_price: Decimal,
    pub market_value: Decimal,
    pub cost_basis: Decimal,
    pub unrealized_pl: Decimal,
    pub unrealized_pl_pct: Decimal,
}

/// Account snapshot
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AccountSnapshot {
    pub id: Uuid,
    pub timestamp: DateTime<Utc>,
    pub equity: Decimal,
    pub cash: Decimal,
    pub buying_power: Decimal,
    pub long_market_value: Decimal,
    pub total_equity: Decimal,
}

/// Kill switch event
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct KillSwitchEvent {
    pub id: Uuid,
    pub reason: String,
    pub timestamp: DateTime<Utc>,
    pub triggered_by: String,
}

/// Risk rejection event
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RiskRejection {
    pub id: Uuid,
    pub decision_id: Uuid,
    pub symbol: String,
    pub reason: String,
    pub timestamp: DateTime<Utc>,
}

/// Market clock status
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MarketClock {
    pub timestamp: DateTime<Utc>,
    pub is_open: bool,
    pub next_open: Option<DateTime<Utc>>,
    pub next_close: Option<DateTime<Utc>>,
}

/// Configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Config {
    pub account: AccountConfig,
    pub session: SessionConfig,
    pub universe: UniverseConfig,
    pub portfolio: PortfolioConfig,
    pub orders: OrdersConfig,
    pub risk: RiskConfig,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AccountConfig {
    pub name: String,
    pub mode: TradingMode,
    pub expected_equity: Decimal,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SessionConfig {
    pub timezone: String,
    pub regular_open: String,
    pub regular_close: String,
    pub place_orders_only_during_market_hours: bool,
    pub no_extended_hours: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct UniverseConfig {
    pub asset_class: AssetClass,
    pub require_active: bool,
    pub require_tradable: bool,
    pub require_fractionable: bool,
    pub allow_etfs: bool,
    pub allow_options: bool,
    pub allow_shorts: bool,
    pub min_price: Decimal,
    pub max_price: Decimal,
    pub min_market_cap: i64,
    pub max_positions: usize,
    pub candidate_limit_per_day: usize,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PortfolioConfig {
    pub target_cash_reserve_pct: Decimal,
    pub max_single_position_pct: Decimal,
    pub starter_position_pct: Decimal,
    pub normal_position_pct: Decimal,
    pub max_new_buys_per_day: usize,
    pub max_sells_per_day: usize,
    pub rebalance_frequency_days: usize,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct OrdersConfig {
    pub default_order_type: OrderType,
    pub time_in_force: TimeInForce,
    pub limit_buy_discount_bps: i64,
    pub limit_sell_premium_bps: i64,
    pub order_timeout_minutes: i64,
    pub allow_market_orders: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RiskConfig {
    pub no_daily_stop_loss: bool,
    pub kill_switch_on_reconcile_failure: bool,
    pub reject_if_market_closed: bool,
    pub reject_if_asset_not_fractionable: bool,
    pub reject_if_not_paper: bool,
}
