//! Alpaca WebSocket stream for order updates (stub for Phase 2).

use anyhow::Result;
use tracing::info;

pub struct AlpacaStream {
    // TODO: Implement WebSocket stream in Phase 7
}

impl AlpacaStream {
    pub fn new() -> Self {
        Self {}
    }

    pub async fn connect(&self) -> Result<()> {
        info!("Would connect to Alpaca WebSocket stream");
        Ok(())
    }

    pub async fn subscribe(&self, symbols: &[String]) -> Result<()> {
        info!("Would subscribe to order updates for {:?}", symbols);
        Ok(())
    }
}
