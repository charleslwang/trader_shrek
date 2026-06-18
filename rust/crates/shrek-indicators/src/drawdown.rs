use rust_decimal::Decimal;
use rust_decimal::prelude::ToPrimitive;
use rust_decimal_macros::dec;

/// Calculate drawdown from peak
pub fn drawdown(current_price: Decimal, peak_price: Decimal) -> Decimal {
    if peak_price == dec!(0) {
        return dec!(0);
    }
    
    let ratio = current_price / peak_price;
    if ratio < dec!(1) {
        dec!(1) - ratio
    } else {
        dec!(0)
    }
}

/// Calculate maximum drawdown from a series of prices
pub fn max_drawdown(prices: &[Decimal]) -> Decimal {
    if prices.is_empty() {
        return dec!(0);
    }

    let mut peak = prices[0];
    let mut max_dd = dec!(0);

    for &price in prices.iter().skip(1) {
        if price > peak {
            peak = price;
        } else {
            let dd = drawdown(price, peak);
            if dd > max_dd {
                max_dd = dd;
            }
        }
    }

    max_dd
}

/// Calculate running peak (highest price seen so far)
pub fn running_peak(prices: &[Decimal]) -> Vec<Decimal> {
    let mut peaks = Vec::with_capacity(prices.len());
    let mut current_peak = dec!(0);

    for &price in prices {
        if price > current_peak {
            current_peak = price;
        }
        peaks.push(current_peak);
    }

    peaks
}

/// Calculate drawdown series from price series
pub fn drawdown_series(prices: &[Decimal]) -> Vec<Decimal> {
    let peaks = running_peak(prices);
    prices
        .iter()
        .zip(peaks.iter())
        .map(|(&price, &peak)| drawdown(price, peak))
        .collect()
}

/// Calculate drawdown quantile from historical drawdowns
pub fn drawdown_quantile(drawdowns: &[Decimal], quantile: Decimal) -> Decimal {
    if drawdowns.is_empty() {
        return dec!(0);
    }

    let mut sorted = drawdowns.to_vec();
    sorted.sort_by(|a, b| a.partial_cmp(b).unwrap());

    let q = quantile.to_f64().unwrap_or(0.0).clamp(0.0, 1.0);
    let index = (((sorted.len() - 1) as f64) * q).ceil() as usize;
    sorted[index]
}

/// Calculate 52-week high
pub fn high_52w(prices: &[Decimal]) -> Option<Decimal> {
    if prices.len() < 252 {
        return None;
    }

    let last_252 = &prices[prices.len() - 252..];
    last_252.iter().max().copied()
}

/// Calculate drawdown from 52-week high
pub fn drawdown_52w(current_price: Decimal, prices: &[Decimal]) -> Option<Decimal> {
    let high = high_52w(prices)?;
    Some(drawdown(current_price, high))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_drawdown() {
        assert_eq!(drawdown(dec!(80), dec!(100)), dec!(0.20));
        assert_eq!(drawdown(dec!(100), dec!(100)), dec!(0));
        assert_eq!(drawdown(dec!(120), dec!(100)), dec!(0));
    }

    #[test]
    fn test_max_drawdown() {
        let prices = vec![dec!(100), dec!(110), dec!(105), dec!(95), dec!(90), dec!(100)];
        let max_dd = max_drawdown(&prices);
        // Peak is 110, low is 90, drawdown = (110-90)/110 = 0.1818
        assert!((max_dd - dec!(0.1818)).abs() < dec!(0.01));
    }

    #[test]
    fn test_drawdown_quantile() {
        let drawdowns = vec![dec!(0.05), dec!(0.10), dec!(0.15), dec!(0.20), dec!(0.25)];
        let q85 = drawdown_quantile(&drawdowns, dec!(0.85));
        // 85th percentile of 5 values is index 4 (0-based)
        assert_eq!(q85, dec!(0.25));
    }
}
