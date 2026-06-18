use rust_decimal::Decimal;
use rust_decimal_macros::dec;

/// Calculate trailing stop price based on percentage
pub fn trailing_stop_pct(entry_price: Decimal, trailing_pct: Decimal) -> Decimal {
    entry_price * (dec!(1) - trailing_pct)
}

/// Calculate trailing stop based on ATR
pub fn trailing_stop_atr(current_price: Decimal, atr: Decimal, atr_multiplier: Decimal) -> Decimal {
    let atr_pct = (atr * atr_multiplier) / current_price;
    current_price * (dec!(1) - atr_pct)
}

/// Calculate running high since entry
pub fn running_high_since_entry(prices: &[Decimal], entry_index: usize) -> Option<Decimal> {
    if entry_index >= prices.len() {
        return None;
    }

    prices[entry_index..].iter().max().copied()
}

/// Calculate current trailing drawdown from running high
pub fn trailing_drawdown(current_price: Decimal, running_high: Decimal) -> Decimal {
    if running_high == dec!(0) {
        return dec!(0);
    }
    
    dec!(1) - (current_price / running_high)
}

/// Check if trailing stop is triggered
pub fn is_trailing_stop_triggered(
    current_price: Decimal,
    running_high: Decimal,
    trailing_threshold: Decimal,
) -> bool {
    let drawdown = trailing_drawdown(current_price, running_high);
    drawdown >= trailing_threshold
}

/// Calculate dynamic trailing threshold based on ATR
pub fn dynamic_trailing_threshold(atr: Decimal, price: Decimal, min_threshold: Decimal) -> Decimal {
    let atr_threshold = (atr * dec!(2.5)) / price;
    atr_threshold.max(min_threshold)
}

/// Check if position has gained enough to activate trailing stop
pub fn should_activate_trailing(current_price: Decimal, entry_price: Decimal, activation_gain: Decimal) -> bool {
    let gain = (current_price / entry_price) - dec!(1);
    gain >= activation_gain
}

/// Calculate trailing stop price with activation gain check
pub fn calculate_trailing_stop_with_activation(
    current_price: Decimal,
    entry_price: Decimal,
    running_high: Decimal,
    atr: Decimal,
    activation_gain: Decimal,
    min_trailing_threshold: Decimal,
) -> Option<Decimal> {
    // Only activate if gain threshold met
    if !should_activate_trailing(current_price, entry_price, activation_gain) {
        return None;
    }

    // Calculate dynamic threshold
    let threshold = dynamic_trailing_threshold(atr, current_price, min_trailing_threshold);
    
    // Calculate stop price
    Some(running_high * (dec!(1) - threshold))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_trailing_stop_pct() {
        let stop = trailing_stop_pct(dec!(100), dec!(0.15));
        assert_eq!(stop, dec!(85));
    }

    #[test]
    fn test_running_high_since_entry() {
        let prices = vec![dec!(100), dec!(105), dec!(110), dec!(108), dec!(112)];
        let high = running_high_since_entry(&prices, 0).unwrap();
        assert_eq!(high, dec!(112));
    }

    #[test]
    fn test_trailing_drawdown() {
        let dd = trailing_drawdown(dec!(90), dec!(100));
        assert_eq!(dd, dec!(0.10));
    }

    #[test]
    fn test_is_trailing_stop_triggered() {
        assert!(is_trailing_stop_triggered(dec!(85), dec!(100), dec!(0.15)));
        assert!(!is_trailing_stop_triggered(dec!(95), dec!(100), dec!(0.15)));
    }

    #[test]
    fn test_should_activate_trailing() {
        assert!(should_activate_trailing(dec!(130), dec!(100), dec!(0.30)));
        assert!(!should_activate_trailing(dec!(120), dec!(100), dec!(0.30)));
    }

    #[test]
    fn test_dynamic_trailing_threshold() {
        let threshold = dynamic_trailing_threshold(dec!(2), dec!(100), dec!(0.15));
        // ATR threshold = (2 * 2.5) / 100 = 0.05
        // min_threshold = 0.15
        // Should return max(0.05, 0.15) = 0.15
        assert_eq!(threshold, dec!(0.15));
    }
}
