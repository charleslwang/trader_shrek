//! Volatility calculations.

use rust_decimal::prelude::*;

/// Calculate range in basis points
pub fn range_bps(high: Decimal, low: Decimal) -> i32 {
    if low.is_zero() {
        return 0;
    }
    let range = (high - low) / low;
    (range * Decimal::from(10_000))
        .to_i32()
        .unwrap_or(0)
}

/// Calculate rolling volatility (standard deviation of returns)
pub fn rolling_volatility(returns: &[Decimal], window: usize) -> Vec<Option<Decimal>> {
    if window == 0 || returns.is_empty() {
        return vec![None; returns.len()];
    }

    let mut result = Vec::with_capacity(returns.len());

    for i in 0..returns.len() {
        if i < window - 1 {
            result.push(None);
            continue;
        }

        let window_returns = &returns[i - window + 1..=i];
        let mean = window_returns.iter().sum::<Decimal>() / Decimal::from(window as i64);
        let variance = window_returns
            .iter()
            .map(|&r| (r - mean) * (r - mean))
            .sum::<Decimal>()
            / Decimal::from(window as i64);

        // Convert to f64 for sqrt, then back to Decimal
        let std_dev = variance.to_f64().map(|v| v.sqrt()).map(Decimal::from_f64);
        result.push(std_dev.flatten());
    }

    result
}

/// Calculate ATR (Average True Range) approximation
pub fn atr(high: Decimal, low: Decimal, prev_close: Decimal) -> Decimal {
    let tr1 = high - low;
    let tr2 = (high - prev_close).abs();
    let tr3 = (low - prev_close).abs();
    tr1.max(tr2).max(tr3)
}

#[cfg(test)]
mod tests {
    use super::*;
    use rust_decimal::prelude::*;

    #[test]
    fn test_range_bps() {
        let high = Decimal::from(105);
        let low = Decimal::from(100);
        let bps = range_bps(high, low);
        assert_eq!(bps, 500);
    }

    #[test]
    fn test_rolling_volatility() {
        let returns = vec![
            Decimal::from_str("0.01").unwrap(),
            Decimal::from_str("0.02").unwrap(),
            Decimal::from_str("-0.01").unwrap(),
            Decimal::from_str("0.03").unwrap(),
            Decimal::from_str("-0.02").unwrap(),
        ];
        let result = rolling_volatility(&returns, 3);
        assert_eq!(result[0], None);
        assert_eq!(result[1], None);
        assert!(result[2].is_some());
    }

    #[test]
    fn test_atr() {
        let high = Decimal::from(105);
        let low = Decimal::from(100);
        let prev_close = Decimal::from(102);
        let atr_val = atr(high, low, prev_close);
        assert_eq!(atr_val, Decimal::from(5)); // high - low
    }
}
