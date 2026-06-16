# 🧟 Shrek Trader

A hybrid Python + Rust algorithmic trading system for same-day online probability microtrading with Alpaca paper trading.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Python Research Layer                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │  Watchlist   │  │   Features   │  │  Online       │     │
│  │  Builder     │  │   Engine     │  │  Models       │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
│         │                  │                  │             │
│         └──────────────────┼──────────────────┘             │
│                            │                                 │
│                    ┌───────▼────────┐                        │
│                    │  Probability  │                        │
│                    │  Ensemble      │                        │
│                    └───────┬────────┘                        │
│                            │                                 │
│                    ┌───────▼────────┐                        │
│                    │  Intent Builder│                        │
│                    └───────┬────────┘                        │
└────────────────────────────┼────────────────────────────────┘
                             │ HTTP POST /intents
┌────────────────────────────▼────────────────────────────────┐
│                    Rust Execution Daemon                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │  Risk Engine │  │ Order Manager│  │  Alpaca API  │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
│         │                  │                  │             │
│         └──────────────────┼──────────────────┘             │
│                            │                                 │
│                    ┌───────▼────────┐                        │
│                    │  HTTP Server   │                        │
│                    │  (axum)        │                        │
│                    └───────┬────────┘                        │
└────────────────────────────┼────────────────────────────────┘
                             │
                    ┌────────▼────────┐
                    │  SQLite DB     │
                    │  (operational) │
                    └─────────────────┘
```

## Setup

### Prerequisites

- Python 3.11+
- Rust 1.70+
- Alpaca paper trading account

### Environment Variables

Copy `.env.example` to `.env` and fill in your Alpaca API keys:

```bash
cp .env.example .env
# Edit .env with your credentials
```

Required variables:
- `ALPACA_API_KEY` - Your Alpaca API key
- `ALPACA_SECRET_KEY` - Your Alpaca secret key
- `SHREK_MODE` - Must be "paper" or "dry-run" (refuses to start otherwise)

### Install Dependencies

```bash
# Python
cd python
pip install -e .

# Rust
cd rust
cargo build --release
```

## How to Run

### Dry-Run Mode (No Alpaca Orders)

```bash
# Terminal 1: Start Rust daemon
cd rust
cargo run -p shrek-exec -- --config ../config/shrek.paper.yaml --dry-run

# Terminal 2: Run orchestrator
cd python
python -m shrek_ai.scripts.dry_run_day
```

### Paper Mode (Alpaca Paper Trading)

```bash
# Terminal 1: Start Rust daemon
cd rust
cargo run -p shrek-exec -- --config ../config/shrek.paper.yaml --paper

# Terminal 2: Run orchestrator
cd python
python -m shrek_ai.scripts.run_shrek_day --paper
```

### Post-Market Report

```bash
cd python
python -m shrek_ai.scripts.postmarket_report
```

## Safety Constraints

- Paper trading only (refuses to start if mode is not "paper" or "dry-run")
- Long-only, no short selling
- Limit orders only, no market orders
- No leverage, no options
- Regular market hours only
- Risk engine validates every trade intent
- Position and exposure limits
- Daily loss limits (soft and hard)
- Order timeouts (unfilled orders cancelled)
- Force flat at 3:55 PM ET
- LLMs can only write reports, never place trades
- Same-day data only (no historical training)

## Testing

**Rust:**
```bash
cd rust
cargo test
```

**Python:**
```bash
cd python
pytest
```

## Project Structure

```
trader_shrek/
├── config/              # Configuration files
├── rust/                # Rust execution daemon
│   ├── crates/
│   │   ├── shrek-core/   # Shared types and utilities
│   │   ├── shrek-exec/  # Execution daemon
│   │   └── shrek-indicators/  # Fast indicator functions
├── python/              # Python research layer
│   └── shrek_ai/        # Research modules and scripts
├── data/                # Data storage
└── tests/               # Tests
```

## License

MIT
