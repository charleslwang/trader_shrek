//! State management for the execution daemon.

use chrono::{DateTime, Utc};
use rust_decimal::Decimal;
use shrek_core::{KillSwitchState, PositionState};
use std::collections::HashMap;
use std::sync::{Arc, RwLock};
use tracing::info;

#[derive(Clone)]
pub struct StateManager {
    positions: Arc<RwLock<HashMap<String, PositionState>>>,
    kill_switch: Arc<RwLock<KillSwitchState>>,
    last_update: Arc<RwLock<DateTime<Utc>>>,
}

impl StateManager {
    pub fn new() -> Self {
        Self {
            positions: Arc::new(RwLock::new(HashMap::new())),
            kill_switch: Arc::new(RwLock::new(KillSwitchState::Off)),
            last_update: Arc::new(RwLock::new(Utc::now())),
        }
    }

    pub fn add_position(&self, position: PositionState) {
        let symbol = position.symbol.clone();
        let mut positions = self.positions.write().unwrap();
        positions.insert(symbol.clone(), position);
        *self.last_update.write().unwrap() = Utc::now();
        info!("Added position for {}", symbol);
    }

    pub fn remove_position(&self, symbol: &str) {
        let mut positions = self.positions.write().unwrap();
        positions.remove(symbol);
        *self.last_update.write().unwrap() = Utc::now();
        info!("Removed position for {}", symbol);
    }

    pub fn get_position(&self, symbol: &str) -> Option<PositionState> {
        let positions = self.positions.read().unwrap();
        positions.get(symbol).cloned()
    }

    pub fn get_all_positions(&self) -> Vec<PositionState> {
        let positions = self.positions.read().unwrap();
        positions.values().cloned().collect()
    }

    pub fn has_position(&self, symbol: &str) -> bool {
        let positions = self.positions.read().unwrap();
        positions.contains_key(symbol)
    }

    pub fn position_count(&self) -> usize {
        let positions = self.positions.read().unwrap();
        positions.len()
    }

    pub fn set_kill_switch(&self, state: KillSwitchState) {
        *self.kill_switch.write().unwrap() = state;
        *self.last_update.write().unwrap() = Utc::now();
        info!("Kill switch set to {:?}", state);
    }

    pub fn get_kill_switch_state(&self) -> KillSwitchState {
        *self.kill_switch.read().unwrap()
    }

    pub fn is_kill_switch_on(&self) -> bool {
        matches!(self.get_kill_switch_state(), KillSwitchState::On)
    }

    pub fn clear_all_positions(&self) {
        let mut positions = self.positions.write().unwrap();
        let count = positions.len();
        positions.clear();
        *self.last_update.write().unwrap() = Utc::now();
        info!("Cleared {} positions", count);
    }
}

impl Default for StateManager {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use shrek_core::SignalId;
    use uuid::Uuid;

    #[test]
    fn test_position_management() {
        let state = StateManager::new();

        let position = PositionState {
            symbol: "TEST".to_string(),
            quantity: Decimal::from(10),
            entry_price: Decimal::from(100),
            current_price: Decimal::from(101),
            unrealized_pnl: Decimal::from(10),
            entry_time: Utc::now(),
            max_hold_minutes: 60,
            stop_price: Some(Decimal::from(99)),
            take_profit_price: Some(Decimal::from(102)),
        };

        assert!(!state.has_position("TEST"));
        assert_eq!(state.position_count(), 0);

        state.add_position(position.clone());
        assert!(state.has_position("TEST"));
        assert_eq!(state.position_count(), 1);

        let retrieved = state.get_position("TEST");
        assert!(retrieved.is_some());
        assert_eq!(retrieved.unwrap().symbol, "TEST");

        state.remove_position("TEST");
        assert!(!state.has_position("TEST"));
        assert_eq!(state.position_count(), 0);
    }

    #[test]
    fn test_kill_switch() {
        let state = StateManager::new();

        assert!(!state.is_kill_switch_on());

        state.set_kill_switch(KillSwitchState::On);
        assert!(state.is_kill_switch_on());

        state.set_kill_switch(KillSwitchState::Off);
        assert!(!state.is_kill_switch_on());
    }

    #[test]
    fn test_clear_all() {
        let state = StateManager::new();

        let position = PositionState {
            symbol: "TEST".to_string(),
            quantity: Decimal::from(10),
            entry_price: Decimal::from(100),
            current_price: Decimal::from(101),
            unrealized_pnl: Decimal::from(10),
            entry_time: Utc::now(),
            max_hold_minutes: 60,
            stop_price: None,
            take_profit_price: None,
        };

        state.add_position(position);
        assert_eq!(state.position_count(), 1);

        state.clear_all_positions();
        assert_eq!(state.position_count(), 0);
    }
}
