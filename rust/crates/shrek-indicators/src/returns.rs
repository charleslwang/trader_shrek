use rust_decimal::Decimal;
use rust_decimal::prelude::{FromPrimitive, ToPrimitive};
use rust_decimal_macros::dec;

/// Calculate simple return
pub fn simple_return(old_price: Decimal, new_price: Decimal) -> Decimal {
    if old_price == dec!(0) {
        dec!(0)
    } else {
        (new_price - old_price) / old_price
    }
}

/// Calculate log return
pub fn log_return(old_price: Decimal, new_price: Decimal) -> Decimal {
    if old_price == dec!(0) || new_price == dec!(0) {
        dec!(0)
    } else {
        let ratio = (new_price / old_price).to_f64().unwrap_or(1.0);
        Decimal::from_f64(ratio.ln()).unwrap_or(dec!(0))
    }
}

/// Calculate annualized return from period return
pub fn annualize_return(period_return: Decimal, periods_per_year: i64) -> Decimal {
    let base = (dec!(1) + period_return).to_f64().unwrap_or(1.0);
    let periods = periods_per_year.clamp(i32::MIN as i64, i32::MAX as i64) as i32;
    Decimal::from_f64(base.powi(periods) - 1.0).unwrap_or(dec!(0))
}

/// Calculate cumulative return from a series of returns
pub fn cumulative_return(returns: &[Decimal]) -> Decimal {
    returns.iter().fold(dec!(1), |acc, r| acc * (dec!(1) + r)) - dec!(1)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_simple_return() {
        assert_eq!(simple_return(dec!(100), dec!(110)), dec!(0.10));
        assert_eq!(simple_return(dec!(100), dec!(90)), dec!(-0.10));
    }

    #[test]
    fn test_cumulative_return() {
        let returns = vec![dec!(0.10), dec!(0.05), dec!(-0.02)];
        let cum = cumulative_return(&returns);
        // (1.10 * 1.05 * 0.98) - 1 = 1.1319 - 1 = 0.1319
        assert!((cum - dec!(0.1319)).abs() < dec!(0.0001));
    }
}
