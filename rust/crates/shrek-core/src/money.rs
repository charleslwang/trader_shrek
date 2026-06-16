//! Money handling using Decimal for precise financial calculations.

use rust_decimal::prelude::*;

/// Basis points (1/100 of 1%)
pub type Bps = i32;

/// Money value represented as Decimal for precision
pub type Money = Decimal;

/// Convert basis points to decimal multiplier
pub fn bps_to_decimal(bps: Bps) -> Decimal {
    Decimal::from(bps) / Decimal::from(10_000)
}

/// Convert decimal to basis points
pub fn decimal_to_bps(value: Decimal) -> Bps {
    (value * Decimal::from(10_000))
        .to_i32()
        .unwrap_or(0)
}

/// Clamp a value between min and max
pub fn clamp(value: Decimal, min: Decimal, max: Decimal) -> Decimal {
    if value < min {
        min
    } else if value > max {
        max
    } else {
        value
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_bps_conversion() {
        assert_eq!(bps_to_decimal(100), Decimal::from_str("0.01").unwrap());
        assert_eq!(bps_to_decimal(50), Decimal::from_str("0.005").unwrap());
        assert_eq!(decimal_to_bps(Decimal::from_str("0.01").unwrap()), 100);
    }

    #[test]
    fn test_clamp() {
        assert_eq!(clamp(Decimal::from(5), Decimal::from(1), Decimal::from(10)), Decimal::from(5));
        assert_eq!(clamp(Decimal::from(0), Decimal::from(1), Decimal::from(10)), Decimal::from(1));
        assert_eq!(clamp(Decimal::from(15), Decimal::from(1), Decimal::from(10)), Decimal::from(10));
    }
}
