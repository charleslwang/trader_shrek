use shrek_core::*;
use sqlx::SqlitePool;
use tracing::debug;

/// Log execution events
#[allow(dead_code)]
pub async fn log_execution_event(
    _pool: &SqlitePool,
    event_type: &str,
    details: &str,
) -> anyhow::Result<()> {
    debug!("Logging execution event: {} - {}", event_type, details);
    
    // This would be expanded to a proper events table
    // For now, we just log via tracing
    
    Ok(())
}

/// Get recent order events for a decision
#[allow(dead_code)]
pub async fn get_decision_events(
    pool: &SqlitePool,
    decision_id: uuid::Uuid,
) -> anyhow::Result<Vec<OrderEvent>> {
    let rows = sqlx::query_as::<_, (String, String, String, String, String, String, Option<String>, Option<String>, String, String, Option<String>, String, Option<String>)>(
        r#"
        SELECT id, decision_id, client_order_id, symbol, side, order_type,
               limit_price, quantity, status, filled_quantity, filled_price, timestamp, broker_order_id
        FROM order_events
        WHERE decision_id = ?
        ORDER BY timestamp DESC
        "#
    )
    .bind(decision_id.to_string())
    .fetch_all(pool)
    .await?;

    let events = rows
        .into_iter()
        .map(|(id, decision_id, client_order_id, symbol, side, order_type, limit_price, quantity, status, filled_quantity, filled_price, timestamp, broker_order_id)| {
            OrderEvent {
                id: uuid::Uuid::parse_str(&id).unwrap_or_default(),
                decision_id: uuid::Uuid::parse_str(&decision_id).unwrap_or_default(),
                client_order_id,
                broker_order_id,
                symbol,
                side: match side.as_str() {
                    "Buy" => Side::Buy,
                    "Sell" => Side::Sell,
                    _ => Side::Buy,
                },
                order_type: match order_type.as_str() {
                    "Limit" => OrderType::Limit,
                    "Market" => OrderType::Market,
                    _ => OrderType::Limit,
                },
                limit_price: limit_price.and_then(|s| s.parse().ok()),
                quantity: quantity.and_then(|s| s.parse().ok()),
                status: match status.as_str() {
                    "New" => OrderStatus::New,
                    "PartiallyFilled" => OrderStatus::PartiallyFilled,
                    "Filled" => OrderStatus::Filled,
                    "Cancelled" => OrderStatus::Cancelled,
                    "Expired" => OrderStatus::Expired,
                    "Rejected" => OrderStatus::Rejected,
                    _ => OrderStatus::New,
                },
                filled_quantity: filled_quantity.parse().unwrap_or_default(),
                filled_price: filled_price.and_then(|s| s.parse().ok()),
                timestamp: chrono::DateTime::parse_from_rfc3339(&timestamp).map(|dt| dt.with_timezone(&chrono::Utc)).unwrap_or_else(|_| chrono::Utc::now()),
            }
        })
        .collect();

    Ok(events)
}
