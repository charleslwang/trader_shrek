use anyhow::{bail, Result};
use shrek_core::*;
use std::sync::Arc;
use tracing::{debug, warn};
use crate::state::AppState;

/// Validate an order proposal against risk rules
pub async fn validate_order(
    state: &AppState,
    proposal: &OrderProposal,
) -> Result<()> {
    // Rule 1: Reject if not paper mode
    if state.mode != TradingMode::Paper && state.mode != TradingMode::DryRun {
        bail!("Live mode is explicitly disabled");
    }

    // Rule 2: Reject if market is closed
    if state.config.risk.reject_if_market_closed {
        let clock = state.alpaca_client.get_clock().await?;
        if !clock.is_open {
            bail!("Market is closed, orders not allowed");
        }
    }

    // Rule 3: Reject shorts
    if matches!(proposal.side, Side::Sell) && proposal.reason.contains("short") {
        bail!("Short selling is not allowed");
    }

    // Rule 4: Reject market orders unless explicitly allowed
    if proposal.order_type == OrderType::Market && !state.config.orders.allow_market_orders {
        bail!("Market orders are not allowed by default");
    }

    // Rule 5: Reject if notional is too small
    if proposal.notional < dec!(1) {
        bail!("Order notional must be at least $1.00");
    }

    // Rule 6: Validate limit price
    if proposal.order_type == OrderType::Limit {
        if let Some(limit_price) = proposal.limit_price {
            if limit_price <= dec!(0) {
                bail!("Limit price must be positive");
            }
        } else {
            bail!("Limit orders require a limit price");
        }
    }

    // Rule 7: Check if asset is fractionable (would need to query Alpaca)
    if state.config.risk.reject_if_asset_not_fractionable {
        // For now, we assume all US equities are fractionable in paper trading
        // In production, this would check the asset's fractionable status
    }

    // Rule 8: Check position size limits
    let account = state.alpaca_client.get_account().await?;
    let max_position_notional = account.equity * state.config.portfolio.max_single_position_pct;
    
    if proposal.notional > max_position_notional {
        bail!("Order notional {} exceeds max position size {}", proposal.notional, max_position_notional);
    }

    // Rule 9: Check buying power
    if proposal.side == Side::Buy {
        if proposal.notional > account.buying_power {
            bail!("Insufficient buying power: need {}, have {}", proposal.notional, account.buying_power);
        }
    }

    debug!("Order passed risk validation: {}", proposal.symbol);
    Ok(())
}

/// Check if kill switch is active
pub async fn is_kill_switch_active(state: &AppState) -> bool {
    // This would check a persistent flag in the database
    // For now, always return false
    false
}
