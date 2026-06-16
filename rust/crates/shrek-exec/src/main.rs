use anyhow::Result;
use axum::Router;
use clap::Parser;
use shrek_core::clock::TradingClock;
use shrek_exec::{
    api::create_api_router,
    config::{load_config, ExecConfig},
    db::Database,
    logs::init_logging,
    risk::RiskEngine,
    state::StateManager,
};
use std::sync::Arc;
use tokio::signal;
use tracing::info;

#[derive(Parser, Debug)]
#[command(author, version, about, long_about = None)]
struct Args {
    /// Path to config file
    #[arg(short, long)]
    config: String,

    /// Run in dry-run mode
    #[arg(long)]
    dry_run: bool,

    /// Run in paper mode
    #[arg(long)]
    paper: bool,
}

#[tokio::main]
async fn main() -> Result<()> {
    let args = Args::parse();

    // Initialize logging
    init_logging();

    // Validate mode
    let mode = if args.dry_run {
        "dry-run"
    } else if args.paper {
        "paper"
    } else {
        "dry-run" // Default to dry-run for safety
    };

    info!("Starting Shrek execution daemon in {} mode", mode);

    // Load config
    let config = load_config(&args.config)?;

    // Validate paper mode
    if mode == "paper" && config.account.mode != "paper" {
        anyhow::bail!("Refusing to start: config mode is not 'paper'");
    }

    // Initialize components
    let db = Arc::new(std::sync::Mutex::new(Database::new("data/db/shrek_exec.sqlite")?));
    let state_manager = Arc::new(StateManager::new());
    let risk_engine = Arc::new(std::sync::Mutex::new(RiskEngine::new(
        config.execution.clone(),
        config.risk.clone(),
        config.scoring.clone(),
        if mode == "dry-run" {
            shrek_core::ExecutionMode::DryRun
        } else {
            shrek_core::ExecutionMode::Paper
        },
    )));

    // Create trading clock
    let clock = TradingClock::new(
        &config.session.timezone,
        &config.session.regular_open,
        &config.session.observe_start,
        &config.session.observe_until,
        &config.session.active_start,
        &config.session.active_end,
        &config.session.flatten_start,
        &config.session.force_flat,
    )?;

    // Build API router
    let app = create_api_router(
        risk_engine,
        state_manager,
        db,
        mode.to_string(),
    );

    // Start server
    let listener = tokio::net::TcpListener::bind("0.0.0.0:8080").await?;
    info!("Server listening on http://0.0.0.0:8080");

    // Graceful shutdown
    axum::serve(listener, app)
        .with_graceful_shutdown(shutdown_signal())
        .await?;

    info!("Server shutdown complete");
    Ok(())
}

async fn shutdown_signal() {
    let ctrl_c = async {
        signal::ctrl_c()
            .await
            .expect("failed to install Ctrl+C handler");
    };

    #[cfg(unix)]
    let terminate = async {
        signal::unix::signal(signal::unix::SignalKind::terminate())
            .expect("failed to install signal handler")
            .recv()
            .await;
    };

    #[cfg(not(unix))]
    let terminate = std::future::pending::<()>();

    tokio::select! {
        _ = ctrl_c => {},
        _ = terminate => {},
    }
}

