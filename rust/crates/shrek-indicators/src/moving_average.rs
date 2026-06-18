use rust_decimal::Decimal;
use rust_decimal_macros::dec;

/// Calculate simple moving average
pub fn simple_moving_average(prices: &[Decimal], period: usize) -> Option<Decimal> {
    if prices.len() < period {
        return None;
    }

    let sum: Decimal = prices[prices.len() - period..].iter().sum();
    Some(sum / Decimal::from(period))
}

/// Calculate exponential moving average
pub fn exponential_moving_average(prices: &[Decimal], period: usize) -> Option<Decimal> {
    if prices.is_empty() {
        return None;
    }

    let multiplier = Decimal::from(2) / (Decimal::from(period) + dec!(1));
    let mut ema = prices[0];

    for price in prices.iter().skip(1) {
        ema = (*price - ema) * multiplier + ema;
    }

    Some(ema)
}

/// Calculate slope of moving average (rate of change)
pub fn ma_slope(prices: &[Decimal], period: usize) -> Option<Decimal> {
    if prices.len() < period + 1 {
        return None;
    }

    let current_ma = simple_moving_average(prices, period)?;
    let prev_prices = &prices[..prices.len() - 1];
    let prev_ma = simple_moving_average(prev_prices, period)?;

    if prev_ma == dec!(0) {
        Some(dec!(0))
    } else {
        Some((current_ma - prev_ma) / prev_ma)
    }
}

/// Check if price is above moving average
pub fn is_above_ma(price: Decimal, ma: Decimal) -> bool {
    price > ma
}

/// Check if price is below moving average
pub fn is_below_ma(price: Decimal, ma: Decimal) -> bool {
    price < ma
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_simple_moving_average() {
        let prices = vec![dec!(100), dec!(101), dec!(102), dec!(103), dec!(104)];
        let sma = simple_moving_average(&prices, 3).unwrap();
        // Latest 3 values: (102 + 103 + 104) / 3 = 103
        assert_eq!(sma, dec!(103));
    }

    #[test]
    fn test_exponential_moving_average() {
        let prices = vec![dec!(100), dec!(101), dec!(102), dec!(103), dec!(104)];
        let ema = exponential_moving_average(&prices, 3).unwrap();
        assert!(ema > dec!(100) && ema < dec!(104));
    }

    #[test]
    fn test_ma_slope() {
        let prices = vec![dec!(100), dec!(101), dec!(102), dec!(103), dec!(104), dec!(105)];
        let slope = ma_slope(&prices, 3).unwrap();
        assert!(slope > dec!(0)); // Positive slope
    }
}
