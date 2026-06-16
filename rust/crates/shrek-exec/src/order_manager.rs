//! Order management for execution (stub for Phase 2).

use anyhow::Result;
use chrono::{DateTime, Utc};
use rust_decimal::Decimal;
use shrek_core::{FillEvent, PositionState, SignalId};
use std::sync::Arc;
use tracing::info;

use crate::{
    alpaca_client::AlpacaClient,
    db::Database,
    risk::RiskEngine,
    state::StateManager,
};

pub struct OrderManager {
    db: Arc<Database>,
    state_manager: Arc<StateManager>,
    risk_engine: Arc<RiskEngine>,
    alpaca_client: Option<Arc<AlpacaClient>>,
    dry_run: bool,
}

impl OrderManager {
    pub fn new(
        db: Arc<Database>,
        state_manager: Arc<StateManager>,
        risk_engine: Arc<RiskEngine>,
        alpaca_client: Option<Arc<AlpacaClient>>,
        dry_run: bool,
    ) -> Self {
        Self {
            db,
            state_manager,
            risk_engine,
            alpaca_client,
            dry_run,
        }
    }

    pub async fn submit_order(
        &self,
        symbol: String,
        side: String,
        notional: Decimal,
        limit_price: Decimal,
        signal_id: SignalId,
    ) -> Result<String> {
        if self.dry_run {
            info!(
                "[DRY-RUN] Would submit order: {} {} {} @ {}",
                side, symbol, notional, limit_price
            );
            return Ok("dry_run_order_id".to_string());
        }

        if let Some(client) = &self.alpaca_client {
            client
                .submit_order(&symbol, &side, notional, limit_price)
                .await
        } else {
            Ok("stub_order_id".to_string())
        }
    }

    pub async fn cancel_order(&self, order_id: &str) -> Result<()> {
        if self.dry_run {
            info!("[DRY-RUN] Would cancel order: {}", order_id);
            return Ok(());
        }

        if let Some(client) = &self.alpaca_client {
            client.cancel_order(order_id).await
        } else {
            Ok(())
        }
    }

    pub async fn record_fill(&self, fill: FillEvent) -> Result<()> {
        self.db.log_fill(&fill)?;
        info!("Recorded fill: {} for {}", fill.fill_id, fill.symbol);
        Ok(())
    }

    pub async fn update_position(&self, position: PositionState) -> Result<()> {
        self.db.update_position(&position)?;
        self.state_manager.add_position(position);
        Ok(())
    }

    pub async fn remove_position(&self, symbol: &str) -> Result<()> {
        self.db.remove_position(symbol)?;
        self.state_manager.remove_position(symbol);
        Ok(())
    }

    pub async fn reconcile(&self) -> Result<()> {
        info!("Reconciling account state with Alpaca...");
        // TODO: Implement actual reconciliation in Phase 7
        Ok(())
    }
}
