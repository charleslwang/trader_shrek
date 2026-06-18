use anyhow::{Context, Result};
use chrono::Utc;
use rust_decimal_macros::dec;
use shrek_core::*;
use std::sync::Arc;
use tracing::{debug, error, info, warn};
use uuid::Uuid;
use crate::{db, state::AppState};

/// Submit an order to Alpaca
/// Returns (client_order_id, broker_order_id)
pub async fn submit_order(
    state: &AppState,
    proposal: &OrderProposal,
) -> Result<(String, String)> {
    info!("Submitting order: {:?} {} notional={}", proposal.side, proposal.symbol, proposal.notional);

    let client_order_id = format!("shrek-{}", Uuid::new_v4());

    // Submit to Alpaca
    let broker_order_id = state
        .alpaca_client
        .submit_order(proposal, &client_order_id)
        .await
        .context("Failed to submit order to Alpaca")?;

    // Log order event
    let event = OrderEvent {
        id: Uuid::new_v4(),
        decision_id: proposal.decision_id,
        client_order_id: client_order_id.clone(),
        broker_order_id: Some(broker_order_id.clone()),
        symbol: proposal.symbol.clone(),
        side: proposal.side,
        order_type: proposal.order_type,
        limit_price: proposal.limit_price,
        quantity: None, // Will be filled by Alpaca
        status: OrderStatus::New,
        filled_quantity: dec!(0),
        filled_price: None,
        timestamp: Utc::now(),
    };

    db::log_order_event(&state.db_pool, &event).await?;

    info!("Order submitted successfully: client_order_id={}, broker_order_id={}", client_order_id, broker_order_id);
    Ok((client_order_id, broker_order_id))
}

/// Cancel all active orders
pub async fn cancel_all_orders(state: &AppState) -> Result<usize> {
    info!("Canceling all orders");

    let canceled = state.alpaca_client.cancel_all_orders().await?;

    info!("Canceled {} orders", canceled);
    Ok(canceled)
}

/// Cancel a specific order
#[allow(dead_code)]
pub async fn cancel_order(state: &AppState, order_id: &str) -> Result<()> {
    info!("Canceling order: {}", order_id);

    state.alpaca_client.cancel_order(order_id).await?;

    info!("Order canceled: {}", order_id);
    Ok(())
}

/// Start the order manager background task
pub async fn start_order_manager(state: Arc<AppState>) {
    info!("Starting order manager");

    let mut interval = tokio::time::interval(tokio::time::Duration::from_secs(60));

    loop {
        interval.tick().await;

        if let Err(e) = check_order_timeouts(&state).await {
            error!("Failed to check order timeouts: {}", e);
        }
    }
}

/// Check for order timeouts and cancel stale orders
async fn check_order_timeouts(state: &AppState) -> Result<()> {
    debug!("Checking for order timeouts");

    // Get active orders from database
    let active_orders = db::get_active_orders(&state.db_pool).await?;

    let now = Utc::now();

    for order in active_orders {
        let elapsed = now.signed_duration_since(order.timestamp);
        let timeout_minutes = state.config.orders.order_timeout_minutes as i64;

        if elapsed.num_minutes() > timeout_minutes {
            let cancel_order_id = order
                .broker_order_id
                .as_deref()
                .unwrap_or(order.client_order_id.as_str());

            warn!(
                "Order {} timed out after {} minutes; canceling broker_order_id={}",
                order.client_order_id,
                elapsed.num_minutes(),
                cancel_order_id,
            );
            
            // Cancel the order
            if let Err(e) = state.alpaca_client.cancel_order(cancel_order_id).await {
                error!("Failed to cancel timed out order {}: {}", cancel_order_id, e);
            }
        }
    }

    Ok(())
}
