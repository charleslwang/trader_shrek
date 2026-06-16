//! Risk engine for validating trade intents.

use chrono::{DateTime, Duration, Utc};
use rust_decimal::Decimal;
use shrek_core::{ExecutionMode, TradeIntent};
use tracing::{debug, info, warn};

use crate::config::{ExecutionConfig, RiskConfig, ScoringConfig};

pub struct RiskEngine {
    execution: ExecutionConfig,
    risk: RiskConfig,
    scoring: ScoringConfig,
    mode: ExecutionMode,
    total_exposure: Decimal,
    trades_today: i64,
    symbol_trades_today: std::collections::HashMap<String, i64>,
    open_orders: std::collections::HashSet<String>,
    open_positions: std::collections::HashSet<String>,
    kill_switch: bool,
}

impl RiskEngine {
    pub fn new(
        execution: ExecutionConfig,
        risk: RiskConfig,
        scoring: ScoringConfig,
        mode: ExecutionMode,
    ) -> Self {
        Self {
            execution,
            risk,
            scoring,
            mode,
            total_exposure: Decimal::ZERO,
            trades_today: 0,
            symbol_trades_today: std::collections::HashMap::new(),
            open_orders: std::collections::HashSet::new(),
            open_positions: std::collections::HashSet::new(),
            kill_switch: false,
        }
    }

    pub fn validate_intent(&mut self, intent: &TradeIntent, now: DateTime<Utc>) -> Result<(), String> {
        // Check kill switch
        if self.kill_switch {
            return Err("Kill switch is active".to_string());
        }

        // Check mode
        if matches!(self.mode, ExecutionMode::Paper) && self.execution.allow_shorts {
            return Err("Shorts not allowed in paper mode".to_string());
        }

        // Check side
        if intent.side != "buy" {
            return Err("Only buy side allowed".to_string());
        }

        // Check notional bounds
        if intent.notional < Decimal::try_from(self.execution.min_position_notional).unwrap_or(Decimal::ZERO) {
            return Err(format!(
                "Notional {} below minimum {}",
                intent.notional, self.execution.min_position_notional
            ));
        }
        if intent.notional > Decimal::try_from(self.execution.max_position_notional).unwrap_or(Decimal::MAX) {
            return Err(format!(
                "Notional {} above maximum {}",
                intent.notional, self.execution.max_position_notional
            ));
        }

        // Check total exposure
        let new_exposure = self.total_exposure + intent.notional;
        if new_exposure > Decimal::try_from(self.execution.max_total_exposure).unwrap_or(Decimal::MAX) {
            return Err(format!(
                "Total exposure {} would exceed maximum {}",
                new_exposure, self.execution.max_total_exposure
            ));
        }

        // Check open positions
        if self.open_positions.contains(&intent.symbol) {
            return Err(format!("Symbol {} already held", intent.symbol));
        }

        // Check open orders
        if self.open_orders.contains(&intent.symbol) {
            return Err(format!("Symbol {} has open order", intent.symbol));
        }

        // Check max trades per day
        if self.trades_today >= 100 {
            return Err("Max trades per day reached".to_string());
        }

        // Check same symbol trades per day
        let symbol_trades = self.symbol_trades_today.get(&intent.symbol).copied().unwrap_or(0);
        if symbol_trades >= self.execution.max_same_symbol_trades_per_day {
            return Err(format!(
                "Max same-symbol trades per day reached for {}",
                intent.symbol
            ));
        }

        // Check signal age
        let signal_age = now.signed_duration_since(intent.timestamp);
        if signal_age > Duration::seconds(self.execution.max_signal_age_seconds) {
            return Err("Signal too old".to_string());
        }

        // Check expected edge
        if intent.expected_edge_bps < self.scoring.min_expected_edge_after_cost_bps as i32 {
            return Err(format!(
                "Expected edge {} below minimum {}",
                intent.expected_edge_bps, self.scoring.min_expected_edge_after_cost_bps
            ));
        }

        // Check spread
        if intent.spread_bps > 25 {
            return Err("Spread too wide".to_string());
        }

        // Check limit price rounding
        if intent.limit_price >= Decimal::ONE {
            if intent.limit_price.scale() > 2 {
                return Err("Limit price has too many decimals for price >= 1".to_string());
            }
        } else {
            if intent.limit_price.scale() > 4 {
                return Err("Limit price has too many decimals for price < 1".to_string());
            }
        }

        debug!("Intent {} passed validation", intent.signal_id);
        Ok(())
    }

    pub fn record_order(&mut self, symbol: String, notional: Decimal) {
        self.open_orders.insert(symbol.clone());
        self.trades_today += 1;
        *self.symbol_trades_today.entry(symbol).or_insert(0) += 1;
    }

    pub fn record_fill(&mut self, symbol: String, notional: Decimal) {
        self.open_orders.remove(&symbol);
        self.open_positions.insert(symbol.clone());
        self.total_exposure += notional;
    }

    pub fn record_position_exit(&mut self, symbol: String, notional: Decimal) {
        self.open_positions.remove(&symbol);
        self.total_exposure -= notional;
    }

    pub fn activate_kill_switch(&mut self, reason: String) {
        warn!("Kill switch activated: {}", reason);
        self.kill_switch = true;
    }

    pub fn deactivate_kill_switch(&mut self) {
        info!("Kill switch deactivated");
        self.kill_switch = false;
    }

    pub fn is_kill_switch_active(&self) -> bool {
        self.kill_switch
    }

    pub fn get_total_exposure(&self) -> Decimal {
        self.total_exposure
    }

    pub fn get_trades_today(&self) -> i64 {
        self.trades_today
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use chrono::Utc;
    use std::str::FromStr;
    use uuid::Uuid;

    fn create_test_intent() -> TradeIntent {
        TradeIntent {
            signal_id: Uuid::new_v4(),
            timestamp: Utc::now(),
            symbol: "TEST".to_string(),
            side: "buy".to_string(),
            notional: Decimal::from(2),
            limit_price: Decimal::from(10),
            horizon_minutes: 5,
            p_up: 0.65,
            expected_edge_bps: 12,
            spread_bps: 10,
            model_version: "test".to_string(),
            feature_snapshot_id: Uuid::new_v4(),
            max_hold_minutes: 8,
            stop_pct: Decimal::from_str("0.005").unwrap(),
            take_profit_pct: Decimal::from_str("0.008").unwrap(),
            reason: "test".to_string(),
        }
    }

    #[test]
    fn test_validate_intent_success() {
        let execution = ExecutionConfig {
            long_only: true,
            allow_shorts: false,
            allow_options: false,
            allow_market_entries: false,
            allow_extended_hours: false,
            entry_order_type: "limit".to_string(),
            time_in_force: "day".to_string(),
            entry_timeout_seconds: 15,
            no_chase_after_cancel: true,
            max_signal_age_seconds: 60,
            limit_price_offset_bps: 2.0,
            min_position_notional: 1.0,
            base_position_notional: 2.0,
            max_position_notional: 3.0,
            max_total_exposure: 60.0,
            max_symbol_exposure: 3.0,
            max_same_symbol_trades_per_day: 3,
        };

        let risk = RiskConfig {
            max_daily_loss: None,
            soft_daily_loss: None,
            stop_after_consecutive_losses: None,
            kill_switch_on_broker_error: true,
            kill_switch_on_reconcile_failure: true,
            reject_stale_signals: true,
            reject_wide_spreads: true,
            reject_duplicate_symbols: true,
            reject_after_flatten_start: true,
        };

        let scoring = ScoringConfig {
            min_expected_edge_after_cost_bps: 7.0,
        };

        let mut engine = RiskEngine::new(execution, risk, scoring, ExecutionMode::DryRun);
        let intent = create_test_intent();

        let result = engine.validate_intent(&intent, Utc::now());
        assert!(result.is_ok());
    }

    #[test]
    fn test_validate_intent_reject_short() {
        let execution = ExecutionConfig {
            long_only: true,
            allow_shorts: false,
            allow_options: false,
            allow_market_entries: false,
            allow_extended_hours: false,
            entry_order_type: "limit".to_string(),
            time_in_force: "day".to_string(),
            entry_timeout_seconds: 15,
            no_chase_after_cancel: true,
            max_signal_age_seconds: 60,
            limit_price_offset_bps: 2.0,
            min_position_notional: 1.0,
            base_position_notional: 2.0,
            max_position_notional: 3.0,
            max_total_exposure: 60.0,
            max_symbol_exposure: 3.0,
            max_same_symbol_trades_per_day: 3,
        };

        let risk = RiskConfig {
            max_daily_loss: None,
            soft_daily_loss: None,
            stop_after_consecutive_losses: None,
            kill_switch_on_broker_error: true,
            kill_switch_on_reconcile_failure: true,
            reject_stale_signals: true,
            reject_wide_spreads: true,
            reject_duplicate_symbols: true,
            reject_after_flatten_start: true,
        };

        let scoring = ScoringConfig {
            min_expected_edge_after_cost_bps: 7.0,
        };

        let mut engine = RiskEngine::new(execution, risk, scoring, ExecutionMode::DryRun);
        let mut intent = create_test_intent();
        intent.side = "sell".to_string();

        let result = engine.validate_intent(&intent, Utc::now());
        assert!(result.is_err());
        assert!(result.unwrap_err().contains("Only buy side allowed"));
    }

    #[test]
    fn test_kill_switch() {
        let execution = ExecutionConfig {
            long_only: true,
            allow_shorts: false,
            allow_options: false,
            allow_market_entries: false,
            allow_extended_hours: false,
            entry_order_type: "limit".to_string(),
            time_in_force: "day".to_string(),
            entry_timeout_seconds: 15,
            no_chase_after_cancel: true,
            max_signal_age_seconds: 60,
            limit_price_offset_bps: 2.0,
            min_position_notional: 1.0,
            base_position_notional: 2.0,
            max_position_notional: 3.0,
            max_total_exposure: 60.0,
            max_symbol_exposure: 3.0,
            max_same_symbol_trades_per_day: 3,
        };

        let risk = RiskConfig {
            max_daily_loss: None,
            soft_daily_loss: None,
            stop_after_consecutive_losses: None,
            kill_switch_on_broker_error: true,
            kill_switch_on_reconcile_failure: true,
            reject_stale_signals: true,
            reject_wide_spreads: true,
            reject_duplicate_symbols: true,
            reject_after_flatten_start: true,
        };

        let scoring = ScoringConfig {
            min_expected_edge_after_cost_bps: 7.0,
        };

        let mut engine = RiskEngine::new(execution, risk, scoring, ExecutionMode::DryRun);
        let intent = create_test_intent();

        engine.activate_kill_switch("test".to_string());
        assert!(engine.is_kill_switch_active());

        let result = engine.validate_intent(&intent, Utc::now());
        assert!(result.is_err());
        assert!(result.unwrap_err().contains("Kill switch is active"));

        engine.deactivate_kill_switch();
        assert!(!engine.is_kill_switch_active());
    }
}
