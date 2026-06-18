use rust_decimal::Decimal;
use rust_decimal_macros::dec;
use crate::types::Position;
use crate::money::{round_to_cents};

/// Calculate portfolio value
pub fn calculate_portfolio_value(cash: Decimal, positions: &[Position]) -> Decimal {
    let positions_value: Decimal = positions.iter().map(|p| p.market_value).sum();
    cash + positions_value
}

/// Calculate cash reserve percentage
pub fn calculate_cash_reserve_pct(cash: Decimal, portfolio_value: Decimal) -> Decimal {
    if portfolio_value == dec!(0) {
        dec!(0)
    } else {
        cash / portfolio_value
    }
}

/// Calculate position percentage of portfolio
pub fn calculate_position_pct(position_market_value: Decimal, portfolio_value: Decimal) -> Decimal {
    if portfolio_value == dec!(0) {
        dec!(0)
    } else {
        position_market_value / portfolio_value
    }
}

/// Check if position exceeds max single position limit
pub fn exceeds_max_position_pct(position_pct: Decimal, max_pct: Decimal) -> bool {
    position_pct > max_pct
}

/// Check if portfolio has too many positions
pub fn exceeds_max_positions(position_count: usize, max_positions: usize) -> bool {
    position_count >= max_positions
}

/// Calculate unrealized P&L percentage
pub fn calculate_unrealized_pl_pct(cost_basis: Decimal, market_value: Decimal) -> Decimal {
    if cost_basis == dec!(0) {
        dec!(0)
    } else {
        (market_value - cost_basis) / cost_basis
    }
}

/// Check if cash reserve is sufficient
pub fn has_sufficient_cash_reserve(cash: Decimal, portfolio_value: Decimal, target_pct: Decimal) -> bool {
    let current_pct = calculate_cash_reserve_pct(cash, portfolio_value);
    current_pct >= target_pct
}

/// Calculate available buying power for new position
pub fn calculate_available_buying_power(
    cash: Decimal,
    portfolio_value: Decimal,
    target_cash_reserve_pct: Decimal,
) -> Decimal {
    let target_reserve = round_to_cents(portfolio_value * target_cash_reserve_pct);
    let available = cash - target_reserve;
    if available < dec!(0) {
        dec!(0)
    } else {
        available
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_calculate_portfolio_value() {
        let cash = dec!(10000);
        let positions = vec![
            Position {
                symbol: "AAPL".to_string(),
                quantity: dec!(10),
                avg_entry_price: dec!(150),
                current_price: dec!(160),
                market_value: dec!(1600),
                cost_basis: dec!(1500),
                unrealized_pl: dec!(100),
                unrealized_pl_pct: dec!(0.0667),
            }
        ];
        assert_eq!(calculate_portfolio_value(cash, &positions), dec!(11600));
    }

    #[test]
    fn test_calculate_cash_reserve_pct() {
        assert_eq!(calculate_cash_reserve_pct(dec!(15000), dec!(100000)), dec!(0.15));
    }

    #[test]
    fn test_exceeds_max_position_pct() {
        assert!(exceeds_max_position_pct(dec!(0.25), dec!(0.20)));
        assert!(!exceeds_max_position_pct(dec!(0.15), dec!(0.20)));
    }

    #[test]
    fn test_exceeds_max_positions() {
        assert!(exceeds_max_positions(12, 12));
        assert!(!exceeds_max_positions(10, 12));
    }

    #[test]
    fn test_has_sufficient_cash_reserve() {
        assert!(has_sufficient_cash_reserve(dec!(15000), dec!(100000), dec!(0.15)));
        assert!(!has_sufficient_cash_reserve(dec!(10000), dec!(100000), dec!(0.15)));
    }
}
