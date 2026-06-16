use anyhow::{Context, Result};
use reqwest::Client;
use serde::{Deserialize, Serialize};
use shrek_core::{TradingMode, *};
use std::sync::Arc;
use tracing::{debug, info, warn};

#[derive(Debug, Serialize)]
struct AlpacaOrderRequest {
    symbol: String,
    side: String,
    #[serde(rename = "type")]
    order_type: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    limit_price: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    qty: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    notional: Option<String>,
    #[serde(rename = "time_in_force")]
    time_in_force: String,
}

#[derive(Debug, Deserialize)]
struct AlpacaOrderResponse {
    id: String,
    client_order_id: String,
    symbol: String,
    side: String,
    #[serde(rename = "type")]
    order_type: String,
    limit_price: Option<String>,
    qty: Option<String>,
    notional: Option<String>,
    filled_qty: Option<String>,
    filled_avg_price: Option<String>,
    status: String,
}

#[derive(Debug, Deserialize)]
struct AlpacaPosition {
    symbol: String,
    qty: String,
    avg_entry_price: String,
    current_price: String,
    market_value: String,
    cost_basis: String,
    unrealized_pl: String,
    unrealized_plpc: String,
}

#[derive(Debug, Deserialize)]
struct AlpacaAccount {
    equity: String,
    cash: String,
    buying_power: String,
    long_market_value: String,
}

#[derive(Debug, Deserialize)]
struct AlpacaClock {
    timestamp: String,
    is_open: bool,
    next_open: String,
    next_close: String,
}

pub struct AlpacaClient {
    client: Client,
    api_key: String,
    secret_key: String,
    base_url: String,
    mode: TradingMode,
}

impl AlpacaClient {
    pub fn new(api_key: String, secret_key: String, base_url: String, mode: TradingMode) -> Self {
        Self {
            client: Client::new(),
            api_key,
            secret_key,
            base_url,
            mode,
        }
    }

    fn auth_headers(&self) -> [(String, String); 2] {
        [
            ("APCA-API-KEY-ID".to_string(), self.api_key.clone()),
            ("APCA-API-SECRET-KEY".to_string(), self.secret_key.clone()),
        ]
    }

    pub async fn submit_order(
        &self,
        proposal: &OrderProposal,
    ) -> Result<String> {
        if self.mode == TradingMode::DryRun {
            info!("Dry-run mode: would submit order for {}", proposal.symbol);
            return Ok("dry-run-order-id".to_string());
        }

        let order_type_str = match proposal.order_type {
            OrderType::Limit => "limit",
            OrderType::Market => "market",
        };

        let side_str = match proposal.side {
            Side::Buy => "buy",
            Side::Sell => "sell",
        };

        let tif_str = match proposal.time_in_force {
            TimeInForce::Day => "day",
            TimeInForce::Gtc => "gtc",
            TimeInForce::Ioc => "ioc",
            TimeInForce::Fok => "fok",
        };

        let mut request = AlpacaOrderRequest {
            symbol: proposal.symbol.clone(),
            side: side_str.to_string(),
            order_type: order_type_str.to_string(),
            limit_price: proposal.limit_price.map(|p| p.to_string()),
            qty: None,
            notional: Some(proposal.notional.to_string()),
            time_in_force: tif_str.to_string(),
        };

        let url = format!("{}/v2/orders", self.base_url);

        let response = self
            .client
            .post(&url)
            .header("APCA-API-KEY-ID", &self.api_key)
            .header("APCA-API-SECRET-KEY", &self.secret_key)
            .json(&request)
            .send()
            .await
            .context("Failed to submit order to Alpaca")?;

        if !response.status().is_success() {
            let error_text = response.text().await.unwrap_or_else(|_| "Unknown error".to_string());
            anyhow::bail!("Alpaca order submission failed: {}", error_text);
        }

        let alpaca_response: AlpacaOrderResponse = response
            .json()
            .await
            .context("Failed to parse Alpaca order response")?;

        info!("Order submitted to Alpaca: {}", alpaca_response.id);
        Ok(alpaca_response.id)
    }

    pub async fn cancel_order(&self, order_id: &str) -> Result<()> {
        if self.mode == TradingMode::DryRun {
            info!("Dry-run mode: would cancel order {}", order_id);
            return Ok(());
        }

        let url = format!("{}/v2/orders/{}", self.base_url, order_id);

        let response = self
            .client
            .delete(&url)
            .header("APCA-API-KEY-ID", &self.api_key)
            .header("APCA-API-SECRET-KEY", &self.secret_key)
            .send()
            .await
            .context("Failed to cancel order")?;

        if !response.status().is_success() {
            warn!("Failed to cancel order {}: status {}", order_id, response.status());
        }

        Ok(())
    }

    pub async fn cancel_all_orders(&self) -> Result<usize> {
        if self.mode == TradingMode::DryRun {
            info!("Dry-run mode: would cancel all orders");
            return Ok(0);
        }

        let url = format!("{}/v2/orders", self.base_url);

        let response = self
            .client
            .delete(&url)
            .header("APCA-API-KEY-ID", &self.api_key)
            .header("APCA-API-SECRET-KEY", &self.secret_key)
            .send()
            .await
            .context("Failed to cancel all orders")?;

        if response.status().is_success() {
            Ok(0) // Alpaca doesn't return count in delete response
        } else {
            Ok(0)
        }
    }

    pub async fn get_positions(&self) -> Result<Vec<Position>> {
        if self.mode == TradingMode::DryRun {
            return Ok(vec![]);
        }

        let url = format!("{}/v2/positions", self.base_url);

        let response = self
            .client
            .get(&url)
            .header("APCA-API-KEY-ID", &self.api_key)
            .header("APCA-API-SECRET-KEY", &self.secret_key)
            .send()
            .await
            .context("Failed to get positions")?;

        if !response.status().is_success() {
            anyhow::bail!("Failed to get positions: {}", response.status());
        }

        let alpaca_positions: Vec<AlpacaPosition> = response
            .json()
            .await
            .context("Failed to parse positions")?;

        let positions = alpaca_positions
            .into_iter()
            .map(|p| Position {
                symbol: p.symbol,
                quantity: p.qty.parse().unwrap_or_default(),
                avg_entry_price: p.avg_entry_price.parse().unwrap_or_default(),
                current_price: p.current_price.parse().unwrap_or_default(),
                market_value: p.market_value.parse().unwrap_or_default(),
                cost_basis: p.cost_basis.parse().unwrap_or_default(),
                unrealized_pl: p.unrealized_pl.parse().unwrap_or_default(),
                unrealized_pl_pct: p.unrealized_plpc.parse().unwrap_or_default(),
            })
            .collect();

        Ok(positions)
    }

    pub async fn get_account(&self) -> Result<AccountSnapshot> {
        if self.mode == TradingMode::DryRun {
            return Ok(AccountSnapshot {
                id: Uuid::new_v4(),
                timestamp: Utc::now(),
                equity: dec!(100),
                cash: dec!(100),
                buying_power: dec!(100),
                long_market_value: dec!(0),
                total_equity: dec!(100),
            });
        }

        let url = format!("{}/v2/account", self.base_url);

        let response = self
            .client
            .get(&url)
            .header("APCA-API-KEY-ID", &self.api_key)
            .header("APCA-API-SECRET-KEY", &self.secret_key)
            .send()
            .await
            .context("Failed to get account")?;

        if !response.status().is_success() {
            anyhow::bail!("Failed to get account: {}", response.status());
        }

        let account: AlpacaAccount = response
            .json()
            .await
            .context("Failed to parse account")?;

        Ok(AccountSnapshot {
            id: Uuid::new_v4(),
            timestamp: Utc::now(),
            equity: account.equity.parse().unwrap_or_default(),
            cash: account.cash.parse().unwrap_or_default(),
            buying_power: account.buying_power.parse().unwrap_or_default(),
            long_market_value: account.long_market_value.parse().unwrap_or_default(),
            total_equity: account.equity.parse().unwrap_or_default(),
        })
    }

    pub async fn get_clock(&self) -> Result<MarketClock> {
        if self.mode == TradingMode::DryRun {
            return Ok(MarketClock {
                timestamp: Utc::now(),
                is_open: is_market_open(),
                next_open: Some(next_market_open()),
                next_close: Some(next_market_close()),
            });
        }

        let url = format!("{}/v2/clock", self.base_url);

        let response = self
            .client
            .get(&url)
            .header("APCA-API-KEY-ID", &self.api_key)
            .header("APCA-API-SECRET-KEY", &self.secret_key)
            .send()
            .await
            .context("Failed to get clock")?;

        if !response.status().is_success() {
            anyhow::bail!("Failed to get clock: {}", response.status());
        }

        let clock: AlpacaClock = response
            .json()
            .await
            .context("Failed to parse clock")?;

        Ok(MarketClock {
            timestamp: Utc::now(),
            is_open: clock.is_open,
            next_open: Some(DateTime::parse_from_rfc3339(&clock.next_open).ok()?.with_timezone(&Utc)),
            next_close: Some(DateTime::parse_from_rfc3339(&clock.next_close).ok()?.with_timezone(&Utc)),
        })
    }
}
