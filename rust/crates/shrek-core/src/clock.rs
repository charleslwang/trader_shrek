use chrono::{DateTime, Utc, Timelike, TimeZone};
use chrono_tz::America::New_York;

/// Check if current time is during regular market hours (9:30 AM - 4:00 PM ET)
pub fn is_market_open() -> bool {
    let now_et = Utc::now().with_timezone(&New_York);
    
    // Check if it's a weekday (Monday=1, Friday=5)
    if now_et.weekday().num_days_from_monday() > 4 {
        return false;
    }
    
    // Check if time is between 9:30 AM and 4:00 PM ET
    let hour = now_et.hour();
    let minute = now_et.minute();
    
    (hour > 9 || (hour == 9 && minute >= 30)) && hour < 16
}

/// Get next market open time
pub fn next_market_open() -> DateTime<Utc> {
    let mut et = Utc::now().with_timezone(&New_York);
    
    // Move to 9:30 AM
    et = et.with_hour(9).unwrap();
    et = et.with_minute(30).unwrap();
    et = et.with_second(0).unwrap();
    et = et.with_nanosecond(0).unwrap();
    
    // If we're past 9:30 AM, move to next day
    let now_et = Utc::now().with_timezone(&New_York);
    if et < now_et {
        et = et + chrono::Duration::days(1);
    }
    
    // If it's a weekend, move to Monday
    while et.weekday().num_days_from_monday() > 4 {
        et = et + chrono::Duration::days(1);
    }
    
    et.with_timezone(&Utc)
}

/// Get next market close time
pub fn next_market_close() -> DateTime<Utc> {
    let mut et = Utc::now().with_timezone(&New_York);
    
    // Move to 4:00 PM
    et = et.with_hour(16).unwrap();
    et = et.with_minute(0).unwrap();
    et = et.with_second(0).unwrap();
    et = et.with_nanosecond(0).unwrap();
    
    // If we're past 4:00 PM, move to next day
    let now_et = Utc::now().with_timezone(&New_York);
    if et < now_et {
        et = et + chrono::Duration::days(1);
    }
    
    // If it's a weekend, move to Monday
    while et.weekday().num_days_from_monday() > 4 {
        et = et + chrono::Duration::days(1);
    }
    
    et.with_timezone(&Utc)
}

/// Check if extended hours are allowed (always false for Shrek)
pub fn extended_hours_allowed() -> bool {
    false
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_extended_hours_always_false() {
        assert!(!extended_hours_allowed());
    }
}
