use shrek_core::*;
use sqlx::SqlitePool;
use std::sync::Arc;
use crate::alpaca_client::AlpacaClient;

/// Application state shared across handlers
pub struct AppState {
    pub config: Config,
    pub mode: TradingMode,
    pub db_pool: SqlitePool,
    pub alpaca_client: Arc<AlpacaClient>,
}
