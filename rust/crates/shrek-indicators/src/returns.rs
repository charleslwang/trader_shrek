//! Return calculations.

use rust_decimal::prelude::*;

/// Calculate simple return from two prices
pub fn simple_return(current: Decimal, previous: Decimal) -> Decimal {
    if previous.is_zero() {
        return Decimal::ZERO;
    }
    (current - previous) / previous
}

/// Calculate return in basis points
pub fn return_bps(current: Decimal, previous: Decimal) -> i32 {
    let ret = simple_return(current, previous);
    (ret * Decimal::from(10_000))
        .to_i32()
        .unwrap_or(0)
}

/// Calculate log return
pub fn log_return(current: Decimal, previous: Decimal) -> f64 {
    if previous.is_zero() || current.is_zero() {
        return 0.0;
    }
    (current.to_f64().unwrap() / previous.to_f64().unwrap()).ln()
}

#[cfg(test)]
mod tests {
    use super::*;
    use rust_decimal::prelude::*;

    #[test]
    fn test_simple_return() {
        let current = Decimal::from(110);
        let previous = Decimal::from(100);
        let ret = simple_return(current, previous);
        assert_eq!(ret, Decimal::from_str("0.1").unwrap());
    }

    #[test]
    fn test_return_bps() {
        let current = Decimal::from(110);
        let previous = Decimal::from(100);
        let bps = return_bps(current, previous);
        assert_eq!(bps, 1000);
    }

    #[test]
    fn test_log_return() {
        let current = Decimal::from(110);
        let previous = Decimal::from(100);
        let ret = log_return(current, previous);
        assert!((ret - 0.09531017980432493).abs() < 1e-10);
    }
}
