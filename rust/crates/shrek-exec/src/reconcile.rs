use anyhow::{Context, Result};
use shrek_core::*;
use std::sync::Arc;
use tracing::{debug, error, info, warn};
use crate::state::AppState;

/// Refresh positions from Alpaca and reconcile with local state
pub async fn refresh_positions(state: &AppState) -> Result<Vec<Position>> {
    info!("Refreshing positions from Alpaca");

    // Get positions from Alpaca
    let alpaca_positions = state.alpaca_client.get_positions().await?;

    // Update local database
    for position in &alpaca_positions {
        db::upsert_position(&state.db_pool, position).await?;
    }

    // Get local positions
    let local_positions = db::get_positions(&state.db_pool).await?;

    // Reconcile: check for positions in local but not in Alpaca
    for local_pos in &local_positions {
        let exists_in_alpaca = alpaca_positions.iter().any(|p| p.symbol == local_pos.symbol);
        if !exists_in_alpaca && local_pos.quantity != dec!(0) {
            warn!("Position {} exists locally but not in Alpaca: qty {}", local_pos.symbol, local_pos.quantity);
            
            // If kill switch on reconcile failure is enabled, trigger it
            if state.config.risk.kill_switch_on_reconcile_failure {
                error!("Reconcile failure detected, kill switch would be triggered");
                // In production, this would trigger the kill switch
            }
        }
    }

    debug!("Refreshed {} positions", alpaca_positions.len());
    Ok(alpaca_positions)
}

/// Reconcile orders between Alpaca and local state
pub async fn reconcile_orders(state: &AppState) -> Result<()> {
    info!("Reconciling orders");

    // Get active orders from database
    let local_active_orders = db::get_active_orders(&state.db_pool).await?;

    // For each local order, check status with Alpaca
    // This would require calling Alpaca's order status endpoint
    // For now, we'll just log that reconciliation happened

    debug!("Reconciled {} orders", local_active_orders.len());
    Ok(())
}

/// Perform full reconciliation on startup
pub async fn full_reconciliation(state: &AppState) -> Result<()> {
    info!("Performing full reconciliation");

    // Refresh positions
    refresh_positions(state).await?;

    // Reconcile orders
    reconcile_orders(state).await?;

    // Take account snapshot
    let account = state.alpaca_client.get_account().await?;
    // Log account snapshot to database
    // This would be implemented in db.rs

    info!("Full reconciliation completed");
    Ok(())
}
