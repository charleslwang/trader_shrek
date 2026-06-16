//! Shrek core types and shared utilities.
//!
//! This crate provides the foundational types used across the Shrek trading system,
//! including money handling, trading clock, and shared data structures.

pub mod clock;
pub mod money;
pub mod rounding;
pub mod types;

pub use types::*;
pub use money::Bps;
