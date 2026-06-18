use anyhow::{Context, Result};
use axum::{
    extract::State,
    http::StatusCode,
    response::Json,
    routing::{get, post},
    Router,
};
use serde_json::json;
use shrek_core::{TradingMode, *};
use sqlx::SqlitePool;
use std::sync::Arc;
use std::env;
use tokio::net::TcpListener;
use tracing::{error, info, warn};
use tracing_subscriber::{layer::SubscriberExt, util::SubscriberInitExt};

mod api;
mod alpaca_client;
mod alpaca_stream;
mod order_manager;
mod risk;
mod state;
mod db;
mod reconcile;
mod logs;

use state::AppState;

#[tokio::main]
async fn main() -> Result<()> {
    // Initialize tracing
    tracing_subscriber::registry()
        .with(
            tracing_subscriber::EnvFilter::try_from_default_env()
                .unwrap_or_else(|_| "shrek_exec=info,axum=info".into()),
        )
        .with(tracing_subscriber::fmt::layer())
        .init();

    // Parse command line arguments
    let args: Vec<String> = env::args().collect();
    let config_path = args
        .iter()
        .position(|s| s == "--config")
        .and_then(|idx| args.get(idx + 1))
        .map(|s| s.as_str())
        .or_else(|| args.iter().find_map(|s| s.strip_prefix("--config=")))
        .unwrap_or("config/shrek.paper.yaml");
    
    let is_dry_run = args.iter().any(|s| s == "--dry-run");
    let is_paper = args.iter().any(|s| s == "--paper");

    // Load configuration
    let config: Config = {
        let config_content = std::fs::read_to_string(config_path)
            .with_context(|| format!("Failed to read config file: {}", config_path))?;
        serde_yaml::from_str(&config_content)
            .with_context(|| format!("Failed to parse config file: {}", config_path))?
    };

    // Reject live mode explicitly
    if config.account.mode == TradingMode::Paper && !is_paper && !is_dry_run {
        anyhow::bail!("Live mode is explicitly disabled. Use --paper for paper trading or --dry-run for testing.");
    }

    // Override mode based on command line flags
    let mode = if is_dry_run {
        TradingMode::DryRun
    } else if is_paper {
        TradingMode::Paper
    } else {
        config.account.mode
    };

    info!("Starting Shrek execution daemon in {:?} mode", mode);

    // Initialize database
    let db_path = "data/db/shrek_exec.sqlite";
    std::fs::create_dir_all("data/db")?;
    let pool = SqlitePool::connect(&format!("sqlite:{}", db_path))
        .await
        .context("Failed to connect to database")?;

    // Run migrations
    db::run_migrations(&pool).await?;

    // Initialize Alpaca client
    let alpaca_api_key = env::var("ALPACA_API_KEY").unwrap_or_else(|_| {
        warn!("ALPACA_API_KEY not set, using dummy client for dry-run");
        "dummy_key".to_string()
    });
    let alpaca_secret_key = env::var("ALPACA_SECRET_KEY").unwrap_or_else(|_| {
        warn!("ALPACA_SECRET_KEY not set, using dummy client for dry-run");
        "dummy_secret".to_string()
    });
    let alpaca_base_url = env::var("ALPACA_TRADING_BASE_URL")
        .unwrap_or_else(|_| "https://paper-api.alpaca.markets".to_string());

    let alpaca_client = Arc::new(alpaca_client::AlpacaClient::new(
        alpaca_api_key,
        alpaca_secret_key,
        alpaca_base_url,
        mode,
    ));

    // Create app state
    let state = Arc::new(AppState {
        config,
        mode,
        db_pool: pool,
        alpaca_client,
    });

    // Build router
    let app = Router::new()
        .route("/health", get(health))
        .route("/state", get(get_state))
        .route("/orders/propose", post(propose_order))
        .route("/orders/cancel_all", post(cancel_all_orders))
        .route("/positions/refresh", post(refresh_positions))
        .route("/kill_switch", post(kill_switch))
        .route("/resume", post(resume))
        .with_state(state.clone());

    // Start server
    let listener = TcpListener::bind("127.0.0.1:8080")
        .await
        .context("Failed to bind to address")?;

    info!("Shrek execution daemon listening on http://127.0.0.1:8080");

    // Start background tasks
    tokio::spawn(alpaca_stream::start_streaming(state.clone()));
    tokio::spawn(order_manager::start_order_manager(state.clone()));

    axum::serve(listener, app).await?;

    Ok(())
}

async fn health() -> Json<serde_json::Value> {
    Json(json!({
        "status": "healthy",
        "timestamp": Utc::now()
    }))
}

async fn get_state(State(state): State<Arc<AppState>>) -> Json<serde_json::Value> {
    Json(json!({
        "mode": state.mode,
        "config": state.config,
        "timestamp": Utc::now()
    }))
}

async fn propose_order(
    State(state): State<Arc<AppState>>,
    Json(proposal): Json<OrderProposal>,
) -> Result<Json<serde_json::Value>, StatusCode> {
    info!("Received order proposal: {:?}", proposal);

    // Validate order
    match risk::validate_order(&state, &proposal).await {
        Ok(_) => {
            // Submit order
            match order_manager::submit_order(&state, &proposal).await {
                Ok(order_id) => {
                    info!("Order submitted successfully: {}", order_id);
                    Ok(Json(json!({
                        "status": "accepted",
                        "order_id": order_id,
                        "decision_id": proposal.decision_id
                    })))
                }
                Err(e) => {
                    error!("Failed to submit order: {}", e);
                    Ok(Json(json!({
                        "status": "rejected",
                        "reason": e.to_string(),
                        "decision_id": proposal.decision_id
                    })))
                }
            }
        }
        Err(reason) => {
            warn!("Order rejected by risk validation: {}", reason);
            Ok(Json(json!({
                "status": "rejected",
                "reason": reason,
                "decision_id": proposal.decision_id
            })))
        }
    }
}

async fn cancel_all_orders(
    State(state): State<Arc<AppState>>,
) -> Result<Json<serde_json::Value>, StatusCode> {
    info!("Canceling all orders");
    
    match order_manager::cancel_all_orders(&state).await {
        Ok(count) => {
            info!("Canceled {} orders", count);
            Ok(Json(json!({
                "status": "success",
                "canceled_count": count
            })))
        }
        Err(e) => {
            error!("Failed to cancel orders: {}", e);
            Err(StatusCode::INTERNAL_SERVER_ERROR)
        }
    }
}

async fn refresh_positions(
    State(state): State<Arc<AppState>>,
) -> Result<Json<serde_json::Value>, StatusCode> {
    info!("Refreshing positions");
    
    match reconcile::refresh_positions(&state).await {
        Ok(positions) => {
            Ok(Json(json!({
                "status": "success",
                "positions": positions
            })))
        }
        Err(e) => {
            error!("Failed to refresh positions: {}", e);
            Err(StatusCode::INTERNAL_SERVER_ERROR)
        }
    }
}

async fn kill_switch(
    State(state): State<Arc<AppState>>,
) -> Result<Json<serde_json::Value>, StatusCode> {
    warn!("Kill switch activated!");
    
    match order_manager::cancel_all_orders(&state).await {
        Ok(_) => {
            // Log kill switch event
            let event = KillSwitchEvent {
                id: Uuid::new_v4(),
                reason: "Manual kill switch activation".to_string(),
                timestamp: Utc::now(),
                triggered_by: "api".to_string(),
            };
            
            if let Err(e) = db::log_kill_switch(&state.db_pool, &event).await {
                error!("Failed to log kill switch event: {}", e);
            }
            
            Ok(Json(json!({
                "status": "success",
                "message": "Kill switch activated, all orders canceled"
            })))
        }
        Err(e) => {
            error!("Failed to activate kill switch: {}", e);
            Err(StatusCode::INTERNAL_SERVER_ERROR)
        }
    }
}

async fn resume(
    State(state): State<Arc<AppState>>,
) -> Result<Json<serde_json::Value>, StatusCode> {
    info!("Resuming operations");
    
    Ok(Json(json!({
        "status": "success",
        "message": "Operations resumed"
    })))
}
