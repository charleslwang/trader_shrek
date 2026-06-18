use rust_decimal::Decimal;
use rust_decimal::prelude::*;
use rust_decimal_macros::dec;

/// Money type for financial calculations
pub type Money = Decimal;

/// Round to 2 decimal places (cents)
pub fn round_to_cents(value: Money) -> Money {
    value.round_dp(2)
}

/// Round to 4 decimal places (for precision calculations)
pub fn round_to_precision(value: Money) -> Money {
    value.round_dp(4)
}

/// Calculate notional from price and quantity
pub fn calculate_notional(price: Money, quantity: Money) -> Money {
    round_to_cents(price * quantity)
}

/// Calculate quantity from notional and price
pub fn calculate_quantity(notional: Money, price: Money) -> Money {
    round_to_precision(notional / price)
}

/// Calculate percentage change
pub fn pct_change(old: Money, new: Money) -> Money {
    if old == dec!(0) {
        dec!(0)
    } else {
        (new - old) / old
    }
}

/// Convert basis points to decimal
pub fn bps_to_decimal(bps: i64) -> Money {
    Decimal::from(bps) / dec!(10000)
}

/// Convert decimal to basis points
pub fn decimal_to_bps(value: Money) -> i64 {
    (value * dec!(10000)).to_i64().unwrap_or(0)
}

/// Calculate dollar value from percentage of equity
pub fn pct_of_equity(equity: Money, pct: Money) -> Money {
    round_to_cents(equity * pct)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_round_to_cents() {
        assert_eq!(round_to_cents(dec!(1.234)), dec!(1.23));
        assert_eq!(round_to_cents(dec!(1.235)), dec!(1.24));
    }

    #[test]
    fn test_calculate_notional() {
        assert_eq!(calculate_notional(dec!(10.50), dec!(5)), dec!(52.50));
    }

    #[test]
    fn test_pct_change() {
        assert_eq!(pct_change(dec!(100), dec!(110)), dec!(0.10));
        assert_eq!(pct_change(dec!(100), dec!(90)), dec!(-0.10));
    }

    #[test]
    fn test_bps_to_decimal() {
        assert_eq!(bps_to_decimal(20), dec!(0.002));
        assert_eq!(bps_to_decimal(100), dec!(0.01));
    }

    #[test]
    fn test_pct_of_equity() {
        assert_eq!(pct_of_equity(dec!(100), dec!(0.10)), dec!(10.00));
    }
}
