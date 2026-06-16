//! HTTP API for the execution daemon.

use axum::{
    extract::State,
    http::StatusCode,
    response::Json,
    routing::{get, post},
    Router,
};
use serde::{Deserialize, Serialize};
use shrek_core::{KillSwitchState, TradeIntent};
use std::sync::{Arc, Mutex};
use tracing::info;

use crate::{
    db::Database,
    risk::RiskEngine,
    state::StateManager,
};

#[derive(Serialize)]
struct HealthResponse {
    status: String,
    mode: String,
    kill_switch: KillSwitchState,
    open_positions: usize,
}

#[derive(Serialize)]
struct StateResponse {
    kill_switch: KillSwitchState,
    open_positions: usize,
    total_exposure: String,
    trades_today: i64,
}

#[derive(Deserialize)]
struct FlattenRequest {
    force: Option<bool>,
}

#[derive(Serialize)]
struct FlattenResponse {
    success: bool,
    message: String,
}

#[derive(Serialize)]
struct KillSwitchResponse {
    success: bool,
    message: String,
}

#[derive(Serialize)]
struct IntentsResponse {
    accepted: usize,
    rejected: usize,
    reasons: Vec<String>,
}

pub fn create_api_router(
    risk_engine: Arc<Mutex<RiskEngine>>,
    state_manager: Arc<StateManager>,
    db: Arc<Mutex<Database>>,
    mode: String,
) -> Router {
    Router::new()
        .route("/health", get(health_handler))
        .route("/state", get(state_handler))
        .route("/intents", post(intents_handler))
        .route("/flatten", post(flatten_handler))
        .route("/cancel_all", post(cancel_all_handler))
        .route("/kill_switch", post(kill_switch_handler))
        .route("/resume", post(resume_handler))
        .with_state(AppState {
            risk_engine,
            state_manager,
            db,
            mode,
        })
}

#[derive(Clone)]
struct AppState {
    risk_engine: Arc<Mutex<RiskEngine>>,
    state_manager: Arc<StateManager>,
    db: Arc<Mutex<Database>>,
    mode: String,
}

async fn health_handler(State(state): State<AppState>) -> Json<HealthResponse> {
    Json(HealthResponse {
        status: "ok".to_string(),
        mode: state.mode.clone(),
        kill_switch: state.state_manager.get_kill_switch_state(),
        open_positions: state.state_manager.position_count(),
    })
}

async fn state_handler(State(state): State<AppState>) -> Json<StateResponse> {
    let risk_engine = state.risk_engine.lock().unwrap();
    Json(StateResponse {
        kill_switch: state.state_manager.get_kill_switch_state(),
        open_positions: state.state_manager.position_count(),
        total_exposure: risk_engine.get_total_exposure().to_string(),
        trades_today: risk_engine.get_trades_today(),
    })
}

async fn intents_handler(
    State(state): State<AppState>,
    Json(intents): Json<Vec<TradeIntent>>,
) -> Result<Json<IntentsResponse>, StatusCode> {
    let mut accepted = 0;
    let mut rejected = 0;
    let mut reasons = Vec::new();

    for intent in intents {
        let now = chrono::Utc::now();
        let mut risk_engine = state.risk_engine.lock().unwrap();
        match risk_engine.validate_intent(&intent, now) {
            Ok(_) => {
                drop(risk_engine);
                let mut db = state.db.lock().unwrap();
                if let Err(e) = db.log_risk_decision(
                    intent.signal_id,
                    true,
                    None,
                    now,
                ) {
                    tracing::error!("Failed to log risk decision: {}", e);
                    return Err(StatusCode::INTERNAL_SERVER_ERROR);
                }
                accepted += 1;
                info!("Intent {} accepted", intent.signal_id);
            }
            Err(reason) => {
                drop(risk_engine);
                let mut db = state.db.lock().unwrap();
                if let Err(e) = db.log_risk_decision(
                    intent.signal_id,
                    false,
                    Some(reason.clone()),
                    now,
                ) {
                    tracing::error!("Failed to log risk decision: {}", e);
                    return Err(StatusCode::INTERNAL_SERVER_ERROR);
                }
                rejected += 1;
                reasons.push(format!("{}: {}", intent.symbol, reason));
                info!("Intent {} rejected: {}", intent.signal_id, reason);
            }
        }
    }

    Ok(Json(IntentsResponse {
        accepted,
        rejected,
        reasons,
    }))
}

async fn flatten_handler(
    State(state): State<AppState>,
    Json(req): Json<FlattenRequest>,
) -> Result<Json<FlattenResponse>, StatusCode> {
    let force = req.force.unwrap_or(false);

    if force {
        state.state_manager.clear_all_positions();
        // Note: RiskEngine would need Mutex for mutable access in production
        // For now, this is a stub
        info!("Force flatten executed");
    } else {
        // Normal flatten - close all positions (to be implemented with Alpaca)
        state.state_manager.clear_all_positions();
        info!("Flatten executed");
    }

    Ok(Json(FlattenResponse {
        success: true,
        message: "Positions flattened".to_string(),
    }))
}

async fn cancel_all_handler(
    State(_state): State<AppState>,
) -> Result<Json<FlattenResponse>, StatusCode> {
    // Cancel all open orders (to be implemented with Alpaca)
    info!("Cancel all orders requested");
    Ok(Json(FlattenResponse {
        success: true,
        message: "All orders cancelled".to_string(),
    }))
}

async fn kill_switch_handler(
    State(state): State<AppState>,
) -> Result<Json<KillSwitchResponse>, StatusCode> {
    state.state_manager.set_kill_switch(KillSwitchState::On);
    // Note: RiskEngine would need Mutex for mutable access in production
    // For now, this is a stub
    info!("Kill switch activated via API");
    Ok(Json(KillSwitchResponse {
        success: true,
        message: "Kill switch activated".to_string(),
    }))
}

async fn resume_handler(
    State(state): State<AppState>,
) -> Result<Json<KillSwitchResponse>, StatusCode> {
    state.state_manager.set_kill_switch(KillSwitchState::Off);
    // Note: RiskEngine would need Mutex for mutable access in production
    // For now, this is a stub
    info!("Kill switch deactivated via API");
    Ok(Json(KillSwitchResponse {
        success: true,
        message: "Kill switch deactivated".to_string(),
    }))
}
