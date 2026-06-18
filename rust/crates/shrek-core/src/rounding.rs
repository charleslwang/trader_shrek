use rust_decimal::Decimal;
use rust_decimal::prelude::*;
use rust_decimal_macros::dec;

/// Round limit price to appropriate precision for US equities
/// US equities typically use 2 decimal places (cents)
pub fn round_limit_price(price: Decimal) -> Decimal {
    price.round_dp(2)
}

/// Round quantity to appropriate precision for fractional shares
/// Fractional shares can use up to 6 decimal places
pub fn round_quantity(quantity: Decimal) -> Decimal {
    quantity.round_dp(6)
}

/// Round notional to cents
pub fn round_notional(notional: Decimal) -> Decimal {
    notional.round_dp(2)
}

/// Apply limit buy discount (in basis points)
pub fn apply_limit_buy_discount(price: Decimal, discount_bps: i64) -> Decimal {
    let discount = Decimal::from(discount_bps) / dec!(10000);
    let discounted = price * (dec!(1) - discount);
    round_limit_price(discounted)
}

/// Apply limit sell premium (in basis points)
pub fn apply_limit_sell_premium(price: Decimal, premium_bps: i64) -> Decimal {
    let premium = Decimal::from(premium_bps) / dec!(10000);
    let premiumed = price * (dec!(1) + premium);
    round_limit_price(premiumed)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_round_limit_price() {
        assert_eq!(round_limit_price(dec!(10.1234)), dec!(10.12));
        assert_eq!(round_limit_price(dec!(10.125)), dec!(10.13));
    }

    #[test]
    fn test_round_quantity() {
        assert_eq!(round_quantity(dec!(5.123456789)), dec!(5.123457));
    }

    #[test]
    fn test_apply_limit_buy_discount() {
        let price = dec!(100.00);
        let discounted = apply_limit_buy_discount(price, 20); // 20 bps = 0.2%
        assert_eq!(discounted, dec!(99.80));
    }

    #[test]
    fn test_apply_limit_sell_premium() {
        let price = dec!(100.00);
        let premiumed = apply_limit_sell_premium(price, 10); // 10 bps = 0.1%
        assert_eq!(premiumed, dec!(100.10));
    }
}
