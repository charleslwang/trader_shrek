//! Trading clock for session time management.

use chrono::{DateTime, NaiveTime, Utc};
use chrono_tz::Tz;
use thiserror::Error;

#[derive(Error, Debug)]
pub enum ClockError {
    #[error("Invalid timezone: {0}")]
    InvalidTimezone(String),
    #[error("Invalid time format: {0}")]
    InvalidTimeFormat(String),
}

/// Trading clock for managing session times
pub struct TradingClock {
    timezone: Tz,
    regular_open: NaiveTime,
    observe_start: NaiveTime,
    observe_until: NaiveTime,
    active_start: NaiveTime,
    active_end: NaiveTime,
    flatten_start: NaiveTime,
    force_flat: NaiveTime,
}

impl TradingClock {
    pub fn new(
        timezone_str: &str,
        regular_open: &str,
        observe_start: &str,
        observe_until: &str,
        active_start: &str,
        active_end: &str,
        flatten_start: &str,
        force_flat: &str,
    ) -> Result<Self, ClockError> {
        let timezone: Tz = timezone_str
            .parse()
            .map_err(|_| ClockError::InvalidTimezone(timezone_str.to_string()))?;

        let parse_time = |s: &str| -> Result<NaiveTime, ClockError> {
            NaiveTime::parse_from_str(s, "%H:%M")
                .map_err(|_| ClockError::InvalidTimeFormat(s.to_string()))
        };

        Ok(Self {
            timezone,
            regular_open: parse_time(regular_open)?,
            observe_start: parse_time(observe_start)?,
            observe_until: parse_time(observe_until)?,
            active_start: parse_time(active_start)?,
            active_end: parse_time(active_end)?,
            flatten_start: parse_time(flatten_start)?,
            force_flat: parse_time(force_flat)?,
        })
    }

    /// Get current time in configured timezone
    pub fn now(&self) -> DateTime<Tz> {
        Utc::now().with_timezone(&self.timezone)
    }

    /// Check if currently in observe-only period
    pub fn is_observe_period(&self) -> bool {
        let now = self.now().time();
        now >= self.observe_start && now < self.observe_until
    }

    /// Check if currently in active trading period
    pub fn is_active_period(&self) -> bool {
        let now = self.now().time();
        now >= self.active_start && now < self.active_end
    }

    /// Check if currently in flatten period
    pub fn is_flatten_period(&self) -> bool {
        let now = self.now().time();
        now >= self.flatten_start && now < self.force_flat
    }

    /// Check if should force flat all positions
    pub fn should_force_flat(&self) -> bool {
        self.now().time() >= self.force_flat
    }

    /// Check if currently in regular market hours
    pub fn is_market_hours(&self) -> bool {
        let now = self.now().time();
        now >= self.regular_open && now < self.force_flat
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_clock_creation() {
        let clock = TradingClock::new(
            "America/New_York",
            "09:30",
            "09:30",
            "10:00",
            "10:00",
            "15:30",
            "15:30",
            "15:55",
        )
        .unwrap();
        assert_eq!(clock.timezone.to_string(), "America/New_York");
    }

    #[test]
    fn test_invalid_timezone() {
        let result = TradingClock::new("Invalid/Timezone", "09:30", "09:30", "10:00", "10:00", "15:30", "15:30", "15:55");
        assert!(result.is_err());
    }
}
