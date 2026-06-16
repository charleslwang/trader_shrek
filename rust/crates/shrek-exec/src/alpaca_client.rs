//! Alpaca client for paper trading (stub for Phase 2).

use anyhow::Result;
use rust_decimal::Decimal;
use tracing::info;

pub struct AlpacaClient {
    api_key: String,
    secret_key: String,
    base_url: String,
}

impl AlpacaClient {
    pub fn new(api_key: String, secret_key: String, base_url: String) -> Self {
        Self {
            api_key,
            secret_key,
            base_url,
        }
    }

    pub async fn submit_order(
        &self,
        symbol: &str,
        side: &str,
        notional: Decimal,
        limit_price: Decimal,
    ) -> Result<String> {
        // TODO: Implement actual Alpaca order submission in Phase 7
        info!(
            "Would submit order: {} {} {} @ {}",
            side, symbol, notional, limit_price
        );
        Ok("stub_order_id".to_string())
    }

    pub async fn cancel_order(&self, order_id: &str) -> Result<()> {
        // TODO: Implement actual Alpaca order cancellation in Phase 7
        info!("Would cancel order: {}", order_id);
        Ok(())
    }

    pub async fn get_account(&self) -> Result<AccountInfo> {
        // TODO: Implement actual Alpaca account fetch in Phase 7
        Ok(AccountInfo {
            equity: Decimal::from(100),
            cash: Decimal::from(100),
            buying_power: Decimal::from(100),
        })
    }

    pub async fn get_positions(&self) -> Result<Vec<Position>> {
        // TODO: Implement actual Alpaca positions fetch in Phase 7
        Ok(vec![])
    }

    pub async fn get_open_orders(&self) -> Result<Vec<Order>> {
        // TODO: Implement actual Alpaca orders fetch in Phase 7
        Ok(vec![])
    }
}

#[derive(Debug)]
pub struct AccountInfo {
    pub equity: Decimal,
    pub cash: Decimal,
    pub buying_power: Decimal,
}

#[derive(Debug)]
pub struct Position {
    pub symbol: String,
    pub quantity: Decimal,
    pub avg_entry_price: Decimal,
    pub current_price: Decimal,
}

#[derive(Debug)]
pub struct Order {
    pub id: String,
    pub symbol: String,
    pub side: String,
    pub quantity: Decimal,
    pub limit_price: Decimal,
    pub status: String,
}
