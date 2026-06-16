//! Shrek execution daemon - Order execution and safety.

pub mod alpaca_client;
pub mod alpaca_stream;
pub mod api;
pub mod config;
pub mod db;
pub mod logs;
pub mod order_manager;
pub mod reconcile;
pub mod risk;
pub mod state;
