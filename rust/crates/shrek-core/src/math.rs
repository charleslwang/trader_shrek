use rust_decimal::Decimal;
use rust_decimal::prelude::*;

/// Calculate expected return from valuation scenarios
pub fn expected_return(
    bear_value: Decimal,
    base_value: Decimal,
    bull_value: Decimal,
    current_price: Decimal,
    p_bear: Decimal,
    p_base: Decimal,
    p_bull: Decimal,
    dividend_yield: Decimal,
) -> Decimal {
    let bear_return = if current_price > dec!(0) {
        (bear_value / current_price) - dec!(1)
    } else {
        dec!(0)
    };
    
    let base_return = if current_price > dec!(0) {
        (base_value / current_price) - dec!(1)
    } else {
        dec!(0)
    };
    
    let bull_return = if current_price > dec!(0) {
        (bull_value / current_price) - dec!(1)
    } else {
        dec!(0)
    };
    
    (p_bear * bear_return) + (p_base * base_return) + (p_bull * bull_return) + dividend_yield
}

/// Calculate downside risk
pub fn downside(bear_value: Decimal, current_price: Decimal) -> Decimal {
    if current_price > dec!(0) {
        let ratio = bear_value / current_price;
        if ratio < dec!(1) {
            dec!(1) - ratio
        } else {
            dec!(0)
        }
    } else {
        dec!(0)
    }
}

/// Calculate upside
pub fn upside(base_value: Decimal, current_price: Decimal) -> Decimal {
    if current_price > dec!(0) {
        let ratio = base_value / current_price;
        if ratio > dec!(1) {
            ratio - dec!(1)
        } else {
            dec!(0)
        }
    } else {
        dec!(0)
    }
}

/// Calculate upside/downside ratio
pub fn upside_downside_ratio(upside: Decimal, downside: Decimal) -> Decimal {
    let epsilon = dec!(0.01);
    let denom = if downside < epsilon { epsilon } else { downside };
    if denom > dec!(0) {
        upside / denom
    } else {
        dec!(0)
    }
}

/// Calculate margin of safety
pub fn margin_of_safety(base_value: Decimal, current_price: Decimal) -> Decimal {
    if base_value > dec!(0) {
        (base_value - current_price) / base_value
    } else {
        dec!(0)
    }
}

/// Calculate Kelly fraction
pub fn kelly_fraction(expected_return: Decimal, volatility: Decimal, risk_free_rate: Decimal) -> Decimal {
    let excess_return = expected_return - risk_free_rate;
    let vol_squared = volatility * volatility;
    
    if vol_squared > dec!(0) {
        excess_return / vol_squared
    } else {
        dec!(0)
    }
}

/// Apply fractional Kelly
pub fn fractional_kelly(kelly: Decimal, fraction: Decimal) -> Decimal {
    kelly * fraction
}

/// Adjust Kelly for confidence and risk
pub fn adjust_kelly_for_risk(
    kelly: Decimal,
    thesis_probability: Decimal,
    risk_penalty: Decimal,
    upside_downside: Decimal,
) -> Decimal {
    let confidence_factor = thesis_probability;
    let risk_factor = dec!(1) - risk_penalty;
    let ud_factor = if upside_downside > dec!(3) {
        dec!(1)
    } else {
        upside_downside / dec!(3)
    };
    
    kelly * confidence_factor * risk_factor * ud_factor
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

/// Calculate drawdown from peak
pub fn drawdown(current_price: Decimal, peak_price: Decimal) -> Decimal {
    if peak_price > dec!(0) {
        dec!(1) - (current_price / peak_price)
    } else {
        dec!(0)
    }
}

/// Calculate trailing stop price
pub fn trailing_stop_price(entry_price: Decimal, trailing_pct: Decimal) -> Decimal {
    entry_price * (dec!(1) - trailing_pct)
}

/// Calculate gain from entry
pub fn gain_from_entry(current_price: Decimal, entry_price: Decimal) -> Decimal {
    if entry_price > dec!(0) {
        (current_price / entry_price) - dec!(1)
    } else {
        dec!(0)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_expected_return() {
        let result = expected_return(
            dec!(80),
            dec!(100),
            dec!(120),
            dec!(100),
            dec!(0.3),
            dec!(0.5),
            dec!(0.2),
            dec!(0.02),
        );
        // Bear: (80/100 - 1) = -0.20, Base: 0.00, Bull: 0.20
        // Expected: 0.3*(-0.20) + 0.5*0.00 + 0.2*0.20 + 0.02 = -0.06 + 0 + 0.04 + 0.02 = 0.00
        assert!((result - dec!(0.00)).abs() < dec!(0.01));
    }

    #[test]
    fn test_downside() {
        assert_eq!(downside(dec!(80), dec!(100)), dec!(0.20));
        assert_eq!(downside(dec!(120), dec!(100)), dec!(0));
    }

    #[test]
    fn test_upside() {
        assert_eq!(upside(dec!(120), dec!(100)), dec!(0.20));
        assert_eq!(upside(dec!(80), dec!(100)), dec!(0));
    }

    #[test]
    fn test_upside_downside_ratio() {
        assert_eq!(upside_downside_ratio(dec!(0.20), dec!(0.10)), dec!(2));
    }

    #[test]
    fn test_margin_of_safety() {
        assert_eq!(margin_of_safety(dec!(100), dec!(80)), dec!(0.20));
    }

    #[test]
    fn test_kelly_fraction() {
        let kelly = kelly_fraction(dec!(0.15), dec!(0.25), dec!(0.04));
        // (0.15 - 0.04) / (0.25^2) = 0.11 / 0.0625 = 1.76
        assert!((kelly - dec!(1.76)).abs() < dec!(0.01));
    }

    #[test]
    fn test_clamp() {
        assert_eq!(clamp(dec!(0.5), dec!(0), dec!(1)), dec!(0.5));
        assert_eq!(clamp(dec!(-0.1), dec!(0), dec!(1)), dec!(0));
        assert_eq!(clamp(dec!(1.5), dec!(0), dec!(1)), dec!(1));
    }

    #[test]
    fn test_drawdown() {
        assert_eq!(drawdown(dec!(80), dec!(100)), dec!(0.20));
    }

    #[test]
    fn test_gain_from_entry() {
        assert_eq!(gain_from_entry(dec!(120), dec!(100)), dec!(0.20));
    }
}
