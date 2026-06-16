use anyhow::{Context, Result};
use chrono::{DateTime, Utc};
use shrek_core::*;
use sqlx::{SqlitePool, sqlite::SqliteQueryAs};
use uuid::Uuid;
use tracing::{debug, error};

/// Run database migrations
pub async fn run_migrations(pool: &SqlitePool) -> Result<()> {
    sqlx::query(
        r#"
        CREATE TABLE IF NOT EXISTS order_events (
            id TEXT PRIMARY KEY,
            decision_id TEXT NOT NULL,
            client_order_id TEXT NOT NULL,
            symbol TEXT NOT NULL,
            side TEXT NOT NULL,
            order_type TEXT NOT NULL,
            limit_price TEXT,
            quantity TEXT,
            status TEXT NOT NULL,
            filled_quantity TEXT NOT NULL,
            filled_price TEXT,
            timestamp TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS order_proposals (
            id TEXT PRIMARY KEY,
            decision_id TEXT NOT NULL,
            symbol TEXT NOT NULL,
            side TEXT NOT NULL,
            notional TEXT NOT NULL,
            order_type TEXT NOT NULL,
            limit_price TEXT,
            time_in_force TEXT NOT NULL,
            reason TEXT NOT NULL,
            source_decision_path TEXT NOT NULL,
            timestamp TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS fills (
            id TEXT PRIMARY KEY,
            order_id TEXT NOT NULL,
            symbol TEXT NOT NULL,
            side TEXT NOT NULL,
            quantity TEXT NOT NULL,
            price TEXT NOT NULL,
            timestamp TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS positions (
            id TEXT PRIMARY KEY,
            symbol TEXT NOT NULL UNIQUE,
            quantity TEXT NOT NULL,
            avg_entry_price TEXT NOT NULL,
            current_price TEXT NOT NULL,
            market_value TEXT NOT NULL,
            cost_basis TEXT NOT NULL,
            unrealized_pl TEXT NOT NULL,
            unrealized_pl_pct TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS account_snapshots (
            id TEXT PRIMARY KEY,
            timestamp TEXT NOT NULL,
            equity TEXT NOT NULL,
            cash TEXT NOT NULL,
            buying_power TEXT NOT NULL,
            long_market_value TEXT NOT NULL,
            total_equity TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS risk_rejections (
            id TEXT PRIMARY KEY,
            decision_id TEXT NOT NULL,
            symbol TEXT NOT NULL,
            reason TEXT NOT NULL,
            timestamp TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS kill_switch_events (
            id TEXT PRIMARY KEY,
            reason TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            triggered_by TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_order_events_decision_id ON order_events(decision_id);
        CREATE INDEX IF NOT EXISTS idx_order_events_timestamp ON order_events(timestamp);
        CREATE INDEX IF NOT EXISTS idx_order_proposals_decision_id ON order_proposals(decision_id);
        CREATE INDEX IF NOT EXISTS idx_positions_symbol ON positions(symbol);
        CREATE INDEX IF NOT EXISTS idx_account_snapshots_timestamp ON account_snapshots(timestamp);
        "#,
    )
    .execute(pool)
    .await
    .context("Failed to run database migrations")?;

    debug!("Database migrations completed");
    Ok(())
}

/// Log an order event
pub async fn log_order_event(pool: &SqlitePool, event: &OrderEvent) -> Result<()> {
    sqlx::query(
        r#"
        INSERT INTO order_events (
            id, decision_id, client_order_id, symbol, side, order_type,
            limit_price, quantity, status, filled_quantity, filled_price, timestamp
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        "#,
    )
    .bind(event.id.to_string())
    .bind(event.decision_id.to_string())
    .bind(&event.client_order_id)
    .bind(&event.symbol)
    .bind(format!("{:?}", event.side))
    .bind(format!("{:?}", event.order_type))
    .bind(event.limit_price.map(|p| p.to_string()))
    .bind(event.quantity.map(|q| q.to_string()))
    .bind(format!("{:?}", event.status))
    .bind(event.filled_quantity.to_string())
    .bind(event.filled_price.map(|p| p.to_string()))
    .bind(event.timestamp.to_rfc3339())
    .execute(pool)
    .await
    .context("Failed to log order event")?;

    debug!("Logged order event: {}", event.id);
    Ok(())
}

/// Log an order proposal
pub async fn log_order_proposal(pool: &SqlitePool, proposal: &OrderProposal) -> Result<()> {
    let id = Uuid::new_v4();
    
    sqlx::query(
        r#"
        INSERT INTO order_proposals (
            id, decision_id, symbol, side, notional, order_type,
            limit_price, time_in_force, reason, source_decision_path, timestamp
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        "#,
    )
    .bind(id.to_string())
    .bind(proposal.decision_id.to_string())
    .bind(&proposal.symbol)
    .bind(format!("{:?}", proposal.side))
    .bind(proposal.notional.to_string())
    .bind(format!("{:?}", proposal.order_type))
    .bind(proposal.limit_price.map(|p| p.to_string()))
    .bind(format!("{:?}", proposal.time_in_force))
    .bind(&proposal.reason)
    .bind(&proposal.source_decision_path)
    .bind(Utc::now().to_rfc3339())
    .execute(pool)
    .await
    .context("Failed to log order proposal")?;

    debug!("Logged order proposal: {}", id);
    Ok(())
}

/// Log a risk rejection
pub async fn log_risk_rejection(pool: &SqlitePool, rejection: &RiskRejection) -> Result<()> {
    sqlx::query(
        r#"
        INSERT INTO risk_rejections (id, decision_id, symbol, reason, timestamp)
        VALUES (?, ?, ?, ?, ?)
        "#,
    )
    .bind(rejection.id.to_string())
    .bind(rejection.decision_id.to_string())
    .bind(&rejection.symbol)
    .bind(&rejection.reason)
    .bind(rejection.timestamp.to_rfc3339())
    .execute(pool)
    .await
    .context("Failed to log risk rejection")?;

    debug!("Logged risk rejection: {}", rejection.id);
    Ok(())
}

/// Log a kill switch event
pub async fn log_kill_switch(pool: &SqlitePool, event: &KillSwitchEvent) -> Result<()> {
    sqlx::query(
        r#"
        INSERT INTO kill_switch_events (id, reason, timestamp, triggered_by)
        VALUES (?, ?, ?, ?)
        "#,
    )
    .bind(event.id.to_string())
    .bind(&event.reason)
    .bind(event.timestamp.to_rfc3339())
    .bind(&event.triggered_by)
    .execute(pool)
    .await
    .context("Failed to log kill switch event")?;

    debug!("Logged kill switch event: {}", event.id);
    Ok(())
}

/// Get active orders (not filled or cancelled)
pub async fn get_active_orders(pool: &SqlitePool) -> Result<Vec<OrderEvent>> {
    let rows = sqlx::query_as::<_, (String, String, String, String, String, String, Option<String>, Option<String>, String, String, Option<String>, String)>(
        r#"
        SELECT id, decision_id, client_order_id, symbol, side, order_type,
               limit_price, quantity, status, filled_quantity, filled_price, timestamp
        FROM order_events
        WHERE status IN ('New', 'PartiallyFilled')
        ORDER BY timestamp DESC
        "#
    )
    .fetch_all(pool)
    .await
    .context("Failed to get active orders")?;

    let orders = rows
        .into_iter()
        .map(|(id, decision_id, client_order_id, symbol, side, order_type, limit_price, quantity, status, filled_quantity, filled_price, timestamp)| {
            OrderEvent {
                id: Uuid::parse_str(&id).unwrap_or_default(),
                decision_id: Uuid::parse_str(&decision_id).unwrap_or_default(),
                client_order_id,
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
                timestamp: DateTime::parse_from_rfc3339(&timestamp).map(|dt| dt.with_timezone(&Utc)).unwrap_or_else(|_| Utc::now()),
            }
        })
        .collect();

    Ok(orders)
}

/// Update position snapshot
pub async fn upsert_position(pool: &SqlitePool, position: &Position) -> Result<()> {
    let id = format!("pos-{}", position.symbol);
    
    sqlx::query(
        r#"
        INSERT INTO positions (
            id, symbol, quantity, avg_entry_price, current_price,
            market_value, cost_basis, unrealized_pl, unrealized_pl_pct, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(symbol) DO UPDATE SET
            quantity = excluded.quantity,
            avg_entry_price = excluded.avg_entry_price,
            current_price = excluded.current_price,
            market_value = excluded.market_value,
            cost_basis = excluded.cost_basis,
            unrealized_pl = excluded.unrealized_pl,
            unrealized_pl_pct = excluded.unrealized_pl_pct,
            updated_at = excluded.updated_at
        "#,
    )
    .bind(id)
    .bind(&position.symbol)
    .bind(position.quantity.to_string())
    .bind(position.avg_entry_price.to_string())
    .bind(position.current_price.to_string())
    .bind(position.market_value.to_string())
    .bind(position.cost_basis.to_string())
    .bind(position.unrealized_pl.to_string())
    .bind(position.unrealized_pl_pct.to_string())
    .bind(Utc::now().to_rfc3339())
    .execute(pool)
    .await
    .context("Failed to upsert position")?;

    debug!("Upserted position: {}", position.symbol);
    Ok(())
}

/// Get all positions
pub async fn get_positions(pool: &SqlitePool) -> Result<Vec<Position>> {
    let rows = sqlx::query_as::<_, (String, String, String, String, String, String, String, String, String)>(
        r#"
        SELECT symbol, quantity, avg_entry_price, current_price,
               market_value, cost_basis, unrealized_pl, unrealized_pl_pct, updated_at
        FROM positions
        ORDER BY symbol
        "#
    )
    .fetch_all(pool)
    .await
    .context("Failed to get positions")?;

    let positions = rows
        .into_iter()
        .map(|(symbol, quantity, avg_entry_price, current_price, market_value, cost_basis, unrealized_pl, unrealized_pl_pct, _)| {
            Position {
                symbol,
                quantity: quantity.parse().unwrap_or_default(),
                avg_entry_price: avg_entry_price.parse().unwrap_or_default(),
                current_price: current_price.parse().unwrap_or_default(),
                market_value: market_value.parse().unwrap_or_default(),
                cost_basis: cost_basis.parse().unwrap_or_default(),
                unrealized_pl: unrealized_pl.parse().unwrap_or_default(),
                unrealized_pl_pct: unrealized_pl_pct.parse().unwrap_or_default(),
            }
        })
        .collect();

    Ok(positions)
}
