//! SQLite database for operational logging.

use anyhow::Result;
use chrono::{DateTime, Utc};
use rusqlite::{params, Connection};
use shrek_core::{FillEvent, OrderState, PositionState, SignalId};
use tracing::info;

pub struct Database {
    conn: Connection,
}

impl Database {
    pub fn new(path: &str) -> Result<Self> {
        let conn = Connection::open(path)?;
        let db = Self { conn };
        db.init_schema()?;
        Ok(db)
    }

    fn init_schema(&self) -> Result<()> {
        self.conn.execute(
            "CREATE TABLE IF NOT EXISTS order_events (
                id TEXT PRIMARY KEY,
                signal_id TEXT NOT NULL,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL,
                notional TEXT NOT NULL,
                limit_price TEXT NOT NULL,
                state TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                reject_reason TEXT
            )",
            [],
        )?;

        self.conn.execute(
            "CREATE TABLE IF NOT EXISTS risk_decisions (
                id TEXT PRIMARY KEY,
                signal_id TEXT NOT NULL,
                accepted BOOLEAN NOT NULL,
                reject_reason TEXT,
                timestamp TEXT NOT NULL
            )",
            [],
        )?;

        self.conn.execute(
            "CREATE TABLE IF NOT EXISTS fills (
                fill_id TEXT PRIMARY KEY,
                signal_id TEXT NOT NULL,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL,
                quantity TEXT NOT NULL,
                fill_price TEXT NOT NULL,
                timestamp TEXT NOT NULL
            )",
            [],
        )?;

        self.conn.execute(
            "CREATE TABLE IF NOT EXISTS positions (
                symbol TEXT PRIMARY KEY,
                quantity TEXT NOT NULL,
                entry_price TEXT NOT NULL,
                current_price TEXT NOT NULL,
                unrealized_pnl TEXT NOT NULL,
                entry_time TEXT NOT NULL,
                max_hold_minutes INTEGER NOT NULL,
                stop_price TEXT,
                take_profit_price TEXT
            )",
            [],
        )?;

        self.conn.execute(
            "CREATE TABLE IF NOT EXISTS account_snapshots (
                id TEXT PRIMARY KEY,
                timestamp TEXT NOT NULL,
                equity TEXT NOT NULL,
                cash TEXT NOT NULL,
                long_market_value TEXT NOT NULL,
                open_positions INTEGER NOT NULL
            )",
            [],
        )?;

        self.conn.execute(
            "CREATE TABLE IF NOT EXISTS kill_switch_events (
                id TEXT PRIMARY KEY,
                state TEXT NOT NULL,
                reason TEXT,
                timestamp TEXT NOT NULL
            )",
            [],
        )?;

        info!("Database schema initialized");
        Ok(())
    }

    pub fn log_risk_decision(
        &self,
        signal_id: SignalId,
        accepted: bool,
        reject_reason: Option<String>,
        timestamp: DateTime<Utc>,
    ) -> Result<()> {
        self.conn.execute(
            "INSERT INTO risk_decisions (id, signal_id, accepted, reject_reason, timestamp)
             VALUES (?1, ?2, ?3, ?4, ?5)",
            params![
                uuid::Uuid::new_v4().to_string(),
                signal_id.to_string(),
                accepted,
                reject_reason,
                timestamp.to_rfc3339(),
            ],
        )?;
        Ok(())
    }

    pub fn log_fill(&self, fill: &FillEvent) -> Result<()> {
        self.conn.execute(
            "INSERT INTO fills (fill_id, signal_id, symbol, side, quantity, fill_price, timestamp)
             VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7)",
            params![
                fill.fill_id.to_string(),
                fill.signal_id.to_string(),
                &fill.symbol,
                &fill.side,
                fill.quantity.to_string(),
                fill.fill_price.to_string(),
                fill.timestamp.to_rfc3339(),
            ],
        )?;
        Ok(())
    }

    pub fn update_position(&self, position: &PositionState) -> Result<()> {
        self.conn.execute(
            "INSERT OR REPLACE INTO positions
             (symbol, quantity, entry_price, current_price, unrealized_pnl, entry_time, max_hold_minutes, stop_price, take_profit_price)
             VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9)",
            params![
                &position.symbol,
                position.quantity.to_string(),
                position.entry_price.to_string(),
                position.current_price.to_string(),
                position.unrealized_pnl.to_string(),
                position.entry_time.to_rfc3339(),
                position.max_hold_minutes,
                position.stop_price.map(|p| p.to_string()),
                position.take_profit_price.map(|p| p.to_string()),
            ],
        )?;
        Ok(())
    }

    pub fn remove_position(&self, symbol: &str) -> Result<()> {
        self.conn.execute("DELETE FROM positions WHERE symbol = ?1", params![symbol])?;
        Ok(())
    }

    pub fn get_open_positions(&self) -> Result<Vec<PositionState>> {
        let mut stmt = self.conn.prepare("SELECT * FROM positions")?;
        let rows = stmt.query_map([], |row| {
            Ok(PositionState {
                symbol: row.get(0)?,
                quantity: row.get::<_, String>(1)?.parse().unwrap_or_default(),
                entry_price: row.get::<_, String>(2)?.parse().unwrap_or_default(),
                current_price: row.get::<_, String>(3)?.parse().unwrap_or_default(),
                unrealized_pnl: row.get::<_, String>(4)?.parse().unwrap_or_default(),
                entry_time: chrono::DateTime::parse_from_rfc3339(&row.get::<_, String>(5)?)
                    .unwrap()
                    .with_timezone(&chrono::Utc),
                max_hold_minutes: row.get(6)?,
                stop_price: row.get::<_, Option<String>>(7)?.and_then(|s| s.parse().ok()),
                take_profit_price: row.get::<_, Option<String>>(8)?.and_then(|s| s.parse().ok()),
            })
        })?;

        let mut positions = Vec::new();
        for row in rows {
            positions.push(row?);
        }
        Ok(positions)
    }
}
