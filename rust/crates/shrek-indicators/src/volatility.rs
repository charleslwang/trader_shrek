use rust_decimal::Decimal;
use rust_decimal::prelude::*;

/// Calculate standard deviation of returns
pub fn standard_deviation(returns: &[Decimal]) -> Decimal {
    if returns.is_empty() {
        return dec!(0);
    }

    let n = Decimal::from(returns.len());
    let mean: Decimal = returns.iter().sum::<Decimal>() / n;
    
    let variance: Decimal = returns
        .iter()
        .map(|r| (*r - mean).powi(2))
        .sum::<Decimal>() / n;
    
    variance.sqrt()
}

/// Calculate annualized volatility from daily returns
pub fn annualized_volatility(daily_returns: &[Decimal]) -> Decimal {
    let daily_vol = standard_deviation(daily_returns);
    daily_vol * dec!(252).sqrt()
}

/// Calculate average true range (ATR)
pub fn average_true_range(high: Decimal, low: Decimal, close: Decimal, prev_close: Decimal) -> Decimal {
    let tr1 = high - low;
    let tr2 = (high - prev_close).abs();
    let tr3 = (low - prev_close).abs();
    
    tr1.max(tr2).max(tr3)
}

/// Calculate ATR over a period (simplified - would need historical data)
pub fn atr_period(highs: &[Decimal], lows: &[Decimal], closes: &[Decimal], period: usize) -> Decimal {
    if highs.len() < period || lows.len() < period || closes.len() < period {
        return dec!(0);
    }

    let mut tr_sum = dec!(0);
    for i in 1..=period {
        let tr = average_true_range(highs[i], lows[i], closes[i], closes[i-1]);
        tr_sum += tr;
    }

    tr_sum / Decimal::from(period)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_standard_deviation() {
        let returns = vec![dec!(0.01), dec!(-0.02), dec!(0.03), dec!(0.01), dec!(-0.01)];
        let std_dev = standard_deviation(&returns);
        assert!(std_dev > dec!(0));
    }

    #[test]
    fn test_average_true_range() {
        let atr = average_true_range(dec!(105), dec!(100), dec!(102), dec!(100));
        // TR = max(105-100=5, |105-100|=5, |100-100|=0) = 5
        assert_eq!(atr, dec!(5));
    }
}
