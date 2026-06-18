use rust_decimal::Decimal;
use std::str::FromStr;

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
    let bear_return = if current_price > Decimal::from_str("0").unwrap() {
        (bear_value / current_price) - Decimal::from_str("1").unwrap()
    } else {
        Decimal::from_str("0").unwrap()
    };
    
    let base_return = if current_price > Decimal::from_str("0").unwrap() {
        (base_value / current_price) - Decimal::from_str("1").unwrap()
    } else {
        Decimal::from_str("0").unwrap()
    };
    
    let bull_return = if current_price > Decimal::from_str("0").unwrap() {
        (bull_value / current_price) - Decimal::from_str("1").unwrap()
    } else {
        Decimal::from_str("0").unwrap()
    };
    
    (p_bear * bear_return) + (p_base * base_return) + (p_bull * bull_return) + dividend_yield
}

/// Calculate downside risk
pub fn downside(bear_value: Decimal, current_price: Decimal) -> Decimal {
    if current_price > Decimal::from_str("0").unwrap() {
        let ratio = bear_value / current_price;
        if ratio < Decimal::from_str("1").unwrap() {
            Decimal::from_str("1").unwrap() - ratio
        } else {
            Decimal::from_str("0").unwrap()
        }
    } else {
        Decimal::from_str("0").unwrap()
    }
}

/// Calculate upside
pub fn upside(base_value: Decimal, current_price: Decimal) -> Decimal {
    if current_price > Decimal::from_str("0").unwrap() {
        let ratio = base_value / current_price;
        if ratio > Decimal::from_str("1").unwrap() {
            ratio - Decimal::from_str("1").unwrap()
        } else {
            Decimal::from_str("0").unwrap()
        }
    } else {
        Decimal::from_str("0").unwrap()
    }
}

/// Calculate upside/downside ratio
pub fn upside_downside_ratio(upside: Decimal, downside: Decimal) -> Decimal {
    let epsilon = Decimal::from_str("0.01").unwrap();
    let denom = if downside < epsilon { epsilon } else { downside };
    if denom > Decimal::from_str("0").unwrap() {
        upside / denom
    } else {
        Decimal::from_str("0").unwrap()
    }
}

/// Calculate margin of safety
pub fn margin_of_safety(base_value: Decimal, current_price: Decimal) -> Decimal {
    if base_value > Decimal::from_str("0").unwrap() {
        (base_value - current_price) / base_value
    } else {
        Decimal::from_str("0").unwrap()
    }
}

/// Calculate Kelly fraction
pub fn kelly_fraction(expected_return: Decimal, volatility: Decimal, risk_free_rate: Decimal) -> Decimal {
    let excess_return = expected_return - risk_free_rate;
    let vol_squared = volatility * volatility;
    
    if vol_squared > Decimal::from_str("0").unwrap() {
        excess_return / vol_squared
    } else {
        Decimal::from_str("0").unwrap()
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
    let risk_factor = Decimal::from_str("1").unwrap() - risk_penalty;
    let ud_factor = if upside_downside > Decimal::from_str("3").unwrap() {
        Decimal::from_str("1").unwrap()
    } else {
        upside_downside / Decimal::from_str("3").unwrap()
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
    if peak_price > Decimal::from_str("0").unwrap() {
        Decimal::from_str("1").unwrap() - (current_price / peak_price)
    } else {
        Decimal::from_str("0").unwrap()
    }
}

/// Calculate trailing stop price
pub fn trailing_stop_price(entry_price: Decimal, trailing_pct: Decimal) -> Decimal {
    entry_price * (Decimal::from_str("1").unwrap() - trailing_pct)
}

/// Calculate gain from entry
pub fn gain_from_entry(current_price: Decimal, entry_price: Decimal) -> Decimal {
    if entry_price > Decimal::from_str("0").unwrap() {
        (current_price / entry_price) - Decimal::from_str("1").unwrap()
    } else {
        Decimal::from_str("0").unwrap()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_expected_return() {
        let result = expected_return(
            Decimal::from_str("80").unwrap(),
            Decimal::from_str("100").unwrap(),
            Decimal::from_str("120").unwrap(),
            Decimal::from_str("100").unwrap(),
            Decimal::from_str("0.3").unwrap(),
            Decimal::from_str("0.5").unwrap(),
            Decimal::from_str("0.2").unwrap(),
            Decimal::from_str("0.02").unwrap(),
        );
        // Bear: (80/100 - 1) = -0.20, Base: 0.00, Bull: 0.20
        // Expected: 0.3*(-0.20) + 0.5*0.00 + 0.2*0.20 + 0.02 = -0.06 + 0 + 0.04 + 0.02 = 0.00
        assert!((result - Decimal::from_str("0.00").unwrap()).abs() < Decimal::from_str("0.01").unwrap());
    }

    #[test]
    fn test_downside() {
        assert_eq!(downside(Decimal::from_str("80").unwrap(), Decimal::from_str("100").unwrap()), Decimal::from_str("0.20").unwrap());
        assert_eq!(downside(Decimal::from_str("120").unwrap(), Decimal::from_str("100").unwrap()), Decimal::from_str("0").unwrap());
    }

    #[test]
    fn test_upside() {
        assert_eq!(upside(Decimal::from_str("120").unwrap(), Decimal::from_str("100").unwrap()), Decimal::from_str("0.20").unwrap());
        assert_eq!(upside(Decimal::from_str("80").unwrap(), Decimal::from_str("100").unwrap()), Decimal::from_str("0").unwrap());
    }

    #[test]
    fn test_upside_downside_ratio() {
        assert_eq!(upside_downside_ratio(Decimal::from_str("0.20").unwrap(), Decimal::from_str("0.10").unwrap()), Decimal::from_str("2").unwrap());
    }

    #[test]
    fn test_margin_of_safety() {
        assert_eq!(margin_of_safety(Decimal::from_str("100").unwrap(), Decimal::from_str("80").unwrap()), Decimal::from_str("0.20").unwrap());
    }

    #[test]
    fn test_kelly_fraction() {
        let kelly = kelly_fraction(Decimal::from_str("0.15").unwrap(), Decimal::from_str("0.25").unwrap(), Decimal::from_str("0.04").unwrap());
        // (0.15 - 0.04) / (0.25^2) = 0.11 / 0.0625 = 1.76
        assert!((kelly - Decimal::from_str("1.76").unwrap()).abs() < Decimal::from_str("0.01").unwrap());
    }

    #[test]
    fn test_clamp() {
        assert_eq!(clamp(Decimal::from_str("0.5").unwrap(), Decimal::from_str("0").unwrap(), Decimal::from_str("1").unwrap()), Decimal::from_str("0.5").unwrap());
        assert_eq!(clamp(Decimal::from_str("-0.1").unwrap(), Decimal::from_str("0").unwrap(), Decimal::from_str("1").unwrap()), Decimal::from_str("0").unwrap());
        assert_eq!(clamp(Decimal::from_str("1.5").unwrap(), Decimal::from_str("0").unwrap(), Decimal::from_str("1").unwrap()), Decimal::from_str("1").unwrap());
    }

    #[test]
    fn test_drawdown() {
        assert_eq!(drawdown(Decimal::from_str("80").unwrap(), Decimal::from_str("100").unwrap()), Decimal::from_str("0.20").unwrap());
    }

    #[test]
    fn test_gain_from_entry() {
        assert_eq!(gain_from_entry(Decimal::from_str("120").unwrap(), Decimal::from_str("100").unwrap()), Decimal::from_str("0.20").unwrap());
    }
}
