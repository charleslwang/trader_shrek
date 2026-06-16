//! VWAP calculations.

use rust_decimal::prelude::*;

/// Calculate VWAP from price and volume data
pub fn vwap(prices: &[Decimal], volumes: &[Decimal]) -> Option<Decimal> {
    if prices.is_empty() || volumes.is_empty() || prices.len() != volumes.len() {
        return None;
    }

    let mut total_value = Decimal::ZERO;
    let mut total_volume = Decimal::ZERO;

    for (price, volume) in prices.iter().zip(volumes.iter()) {
        total_value += price * volume;
        total_volume += volume;
    }

    if total_volume.is_zero() {
        return None;
    }

    Some(total_value / total_volume)
}

/// Calculate distance from VWAP in basis points
pub fn distance_from_vwap_bps(price: Decimal, vwap: Decimal) -> i32 {
    if vwap.is_zero() {
        return 0;
    }
    let distance = (price - vwap) / vwap;
    (distance * Decimal::from(10_000))
        .to_i32()
        .unwrap_or(0)
}

#[cfg(test)]
mod tests {
    use super::*;
    use rust_decimal::prelude::*;

    #[test]
    fn test_vwap() {
        let prices = vec![
            Decimal::from(10),
            Decimal::from(11),
            Decimal::from(12),
        ];
        let volumes = vec![
            Decimal::from(100),
            Decimal::from(200),
            Decimal::from(300),
        ];

        let result = vwap(&prices, &volumes);
        assert!(result.is_some());

        // VWAP = (10*100 + 11*200 + 12*300) / (100 + 200 + 300)
        // = (1000 + 2200 + 3600) / 600
        // = 6800 / 600 = 11.333...
        let expected = Decimal::from_str("11.333333333333333333333333333").unwrap();
        assert!((result.unwrap() - expected).abs() < Decimal::from_str("0.001").unwrap());
    }

    #[test]
    fn test_distance_from_vwap_bps() {
        let price = Decimal::from(110);
        let vwap = Decimal::from(100);
        let bps = distance_from_vwap_bps(price, vwap);
        assert_eq!(bps, 1000);
    }
}
