//! Price rounding utilities for Alpaca decimal rules.

use rust_decimal::Decimal;

/// Round price according to Alpaca decimal rules:
/// - price >= 1.0: max 2 decimals
/// - price < 1.0: max 4 decimals
pub fn round_alpaca_price(price: Decimal) -> Decimal {
    if price >= Decimal::ONE {
        price.round_dp(2)
    } else {
        price.round_dp(4)
    }
}

/// Round notional to 2 decimal places (cents)
pub fn round_notional(notional: Decimal) -> Decimal {
    notional.round_dp(2)
}

#[cfg(test)]
mod tests {
    use super::*;
    use rust_decimal::prelude::*;

    #[test]
    fn test_round_alpaca_price_high() {
        let price = Decimal::from_str("123.456789").unwrap();
        let rounded = round_alpaca_price(price);
        assert_eq!(rounded, Decimal::from_str("123.46").unwrap());
    }

    #[test]
    fn test_round_alpaca_price_low() {
        let price = Decimal::from_str("0.123456").unwrap();
        let rounded = round_alpaca_price(price);
        assert_eq!(rounded, Decimal::from_str("0.1235").unwrap());
    }

    #[test]
    fn test_round_notional() {
        let notional = Decimal::from_str("2.3456").unwrap();
        let rounded = round_notional(notional);
        assert_eq!(rounded, Decimal::from_str("2.35").unwrap());
    }
}
