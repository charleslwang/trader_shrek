//! Rolling window calculations.

use rust_decimal::prelude::*;

/// Calculate rolling mean
pub fn rolling_mean(values: &[Decimal], window: usize) -> Vec<Option<Decimal>> {
    if window == 0 || values.is_empty() {
        return vec![None; values.len()];
    }

    let mut result = Vec::with_capacity(values.len());
    let mut sum = Decimal::ZERO;
    let mut count = 0;

    for (i, &val) in values.iter().enumerate() {
        sum += val;
        count += 1;

        if count > window {
            sum -= values[i - window];
            count -= 1;
        }

        if count >= window {
            result.push(Some(sum / Decimal::from(count as i64)));
        } else {
            result.push(None);
        }
    }

    result
}

/// Calculate rolling standard deviation
pub fn rolling_std(values: &[Decimal], window: usize) -> Vec<Option<Decimal>> {
    if window == 0 || values.is_empty() {
        return vec![None; values.len()];
    }

    let means = rolling_mean(values, window);
    let mut result = Vec::with_capacity(values.len());

    for (i, _val) in values.iter().enumerate() {
        if let Some(mean) = means[i] {
            let start = if i >= window - 1 { i - window + 1 } else { 0 };
            let end = i + 1;
            let window_values = &values[start..end];

            let variance = window_values
                .iter()
                .map(|&v| (v - mean) * (v - mean))
                .sum::<Decimal>()
                / Decimal::from(window as i64);

            // Convert to f64 for sqrt, then back to Decimal
            let std_dev = variance.to_f64().map(|v| v.sqrt()).map(Decimal::from_f64);
            result.push(std_dev.flatten());
        } else {
            result.push(None);
        }
    }

    result
}

/// Calculate z-score
pub fn z_score(value: Decimal, mean: Decimal, std: Decimal) -> f64 {
    if std.is_zero() {
        return 0.0;
    }
    ((value - mean) / std).to_f64().unwrap_or(0.0)
}

/// Clamp value between min and max
pub fn clamp(value: Decimal, min: Decimal, max: Decimal) -> Decimal {
    if value < min {
        min
    } else if value > max {
        max
    } else {
        value
    }
}

/// Calculate percentile rank
pub fn percentile_rank(value: Decimal, values: &[Decimal]) -> f64 {
    if values.is_empty() {
        return 0.5;
    }

    let count = values.iter().filter(|&&v| v < value).count();
    count as f64 / values.len() as f64
}

#[cfg(test)]
mod tests {
    use super::*;
    use rust_decimal::prelude::*;

    #[test]
    fn test_rolling_mean() {
        let values = vec![
            Decimal::from(1),
            Decimal::from(2),
            Decimal::from(3),
            Decimal::from(4),
            Decimal::from(5),
        ];
        let result = rolling_mean(&values, 3);
        assert_eq!(result[0], None);
        assert_eq!(result[1], None);
        assert_eq!(result[2], Some(Decimal::from(2)));
        assert_eq!(result[3], Some(Decimal::from(3)));
        assert_eq!(result[4], Some(Decimal::from(4)));
    }

    #[test]
    fn test_z_score() {
        let value = Decimal::from(15);
        let mean = Decimal::from(10);
        let std = Decimal::from(2);
        let z = z_score(value, mean, std);
        assert!((z - 2.5).abs() < 0.01);
    }

    #[test]
    fn test_clamp() {
        assert_eq!(clamp(Decimal::from(5), Decimal::from(1), Decimal::from(10)), Decimal::from(5));
        assert_eq!(clamp(Decimal::from(0), Decimal::from(1), Decimal::from(10)), Decimal::from(1));
        assert_eq!(clamp(Decimal::from(15), Decimal::from(1), Decimal::from(10)), Decimal::from(10));
    }

    #[test]
    fn test_percentile_rank() {
        let values = vec![
            Decimal::from(1),
            Decimal::from(2),
            Decimal::from(3),
            Decimal::from(4),
            Decimal::from(5),
        ];
        assert_eq!(percentile_rank(Decimal::from(3), &values), 0.4);
        assert_eq!(percentile_rank(Decimal::from(6), &values), 1.0);
        assert_eq!(percentile_rank(Decimal::from(0), &values), 0.0);
    }
}
