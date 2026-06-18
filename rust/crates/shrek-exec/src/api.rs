use axum::{
    extract::State,
    http::StatusCode,
    response::Json,
};
use chrono::Utc;
use serde_json::json;
use shrek_core::*;
use std::sync::Arc;
use crate::state::AppState;

/// Health check endpoint
pub async fn health_check() -> Json<serde_json::Value> {
    Json(json!({
        "status": "healthy",
        "service": "shrek-exec",
        "version": "0.1.0"
    }))
}

/// Get current state
pub async fn get_current_state(
    State(state): State<Arc<AppState>>,
) -> Json<serde_json::Value> {
    Json(json!({
        "mode": state.mode,
        "account_name": state.config.account.name,
        "expected_equity": state.config.account.expected_equity,
        "timestamp": Utc::now()
    }))
}
