# Shrek

Shrek is a slow, AI-assisted, long-term fundamental investing agent that uses LLMs for market research, SEC filing analysis, earnings/news interpretation, thesis tracking, and risk analysis, while deterministic math controls valuation, portfolio scoring, position sizing, entry timing, exits, and Alpaca order execution.

## What Shrek Is

- **AI-assisted long-term fundamental investing** with mathematical entry/exit discipline
- **Slow compounder**: holds positions for weeks, months, or years
- **Paper trading only**: live mode is explicitly disabled
- **Limit orders only**: no market entries by default
- **Long-only**: no shorts, no options
- **Fractional positions**: uses Alpaca fractional trading
- **LLM-grounded research**: uses LLMs to read and reason over financial documents
- **Deterministic execution**: every order must pass mathematical validation before submission

## What Shrek Is Not

- **Not an intraday microtrading bot**: Shrek does not scalp or day trade
- **Not Ninja**: Ninja is the fast quantitative intraday experiment; Shrek is the slow AI fundamental compounder
- **Not a force-flat system**: Shrek does not force-flat daily; positions are long-term
- **Not a live trading system**: live mode is disabled by default and will exit with an error
- **Not a discretionary trader**: all decisions follow deterministic mathematical rules
- **Not a high-frequency system**: Shrek places orders during regular market hours only

## Shrek vs Ninja

| Aspect | Shrek | Ninja |
|--------|-------|-------|
| Time Horizon | Weeks to months | Intraday |
| Strategy | Fundamental investing | Quantitative trading |
| Research | LLM-based fundamental analysis | Technical indicators |
| Execution | Limit orders, fractional shares | Market orders, full shares |
| Position Holding | Overnight, long-term | Intraday only, force-flat |
| Order Type | Limit orders only | Market orders allowed |
| Shorting | No | Yes |
| Options | No | Yes |
| Speed | Slow, deliberate | Fast, reactive |

## System Architecture

Shrek uses a hybrid Python + Rust architecture:

### Python Responsibilities
- SEC filing retrieval and parsing
- Financial statement processing
- LLM research agents
- Multi-agent debate system (optional)
- Retrieval-augmented generation
- Company memory
- Valuation models
- Factor scoring
- Bayesian thesis updates
- Portfolio optimization
- Entry/exit decision generation
- Post-market research memos
- Backtesting/replay
- Analytics

### Rust Responsibilities
- Alpaca trading API execution
- Order submission
- Order update streaming
- Position reconciliation
- Portfolio/account state
- Kill switch
- Order validation
- Limit-order management
- Execution logs
- Safety checks

## Multi-Agent Debate System (Optional)

Shrek can operate in multi-agent mode where two AI agents with opposing perspectives debate investment decisions until reaching consensus.

### Configuration

Enable multi-agent mode in `config/shrek.paper.yaml`:

```yaml
llm:
  enabled: true
  runtime: openai  # Options: ollama, openai, huggingface
  model: gpt-4o
  api_key_env: OPENAI_API_KEY
  base_url: https://api.openai.com/v1

multi_agent:
  enabled: true
  max_conversation_rounds: 5
  consensus_threshold: 0.80
  log_debates: true
  
  agent_1:
    name: "analyst_a"
    runtime: openai  # Different runtime for adversarial diversity
    model: gpt-4o
    api_key_env: OPENAI_API_KEY
    base_url: https://api.openai.com/v1
    role: "bullish_analyst"
    personality: "optimistic_growth_focused"
    
  agent_2:
    name: "analyst_b"
    runtime: huggingface  # Different runtime and model for adversarial diversity
    model: Qwen/Qwen2.5-72B-Instruct
    api_key_env: HF_API_KEY
    base_url: https://api-inference.huggingface.co/models
    role: "bearish_analyst"
    personality: "conservative_risk_focused"
```

### Supported LLM Backends

Shrek supports three LLM backends:

**1. OpenAI (Recommended for Production)**
- Models: `gpt-4o`, `gpt-4-turbo`, `gpt-3.5-turbo`
- Best for: Deep financial analysis, complex reasoning, SEC filing interpretation
- Pros: Highest quality, excellent for research, strong JSON support
- Cons: API costs, rate limits
- Setup: Set `OPENAI_API_KEY` environment variable

**2. HuggingFace (Recommended for Cost-Effective)**
- Models: `Qwen/Qwen2.5-72B-Instruct`, `meta-llama/Llama-3.1-70B-Instruct`, `mistralai/Mistral-Large-Instruct-2407`
- Best for: Cost-effective large models, adversarial diversity
- Pros: Free tier available, many open-source models, adversarial model diversity
- Cons: Inference API can be slower, no native chat (converts to prompt)
- Setup: Set `HF_API_KEY` environment variable

**3. Ollama (Recommended for Local/Privacy)**
- Models: `qwen3:8b`, `llama3:8b`, `mistral:7b`
- Best for: Local execution, privacy, no API costs
- Pros: Free, local, no data leaves your machine
- Cons: Limited to smaller models (8B), less capable for deep research
- Setup: Install Ollama, run `ollama serve`

### Recommended Model Combinations for Adversarial Convergence

For effective adversarial convergence, use different model families:

**Laptop-Friendly (Current Config):**
- Agent 1: `deepseek-r1:8b` (Ollama) - Strong reasoning, 8B distilled model
- Agent 2: `qwen3:8b` (Ollama) - Different model family, 8B
- Both run locally on laptop via Ollama
- Setup: `ollama pull deepseek-r1:8b` and `ollama pull qwen3:8b`

**High-End (Best Quality):**
- Agent 1: `gpt-4o` (OpenAI) - Strong reasoning, bullish perspective
- Agent 2: `Qwen/Qwen2.5-72B-Instruct` (HF) - Different training, bearish perspective

**Cost-Effective:**
- Agent 1: `gpt-4o-mini` (OpenAI) - Good quality, lower cost
- Agent 2: `meta-llama/Llama-3.1-70B-Instruct` (HF) - Large open-source model

### Model Capabilities for Financial Research

**Best for Deep Financial Research:**
1. **gpt-4o** - Strongest reasoning, excellent for complex financial analysis
2. **Qwen2.5-72B-Instruct** - Large open-source model, good financial understanding
3. **Llama-3.1-70B-Instruct** - Strong general reasoning, good for financial tasks

**Adequate for Basic Research:**
1. **gpt-4o-mini** - Good quality, faster and cheaper
2. **Mistral-Large-Instruct-2407** - Strong open-source model
3. **qwen3:8b** - Adequate for simpler analysis tasks

**Laptop-Friendly (Local Deployment):**
1. **deepseek-r1:8b** - Strong reasoning (97.3% MATH-500), chain-of-thought
2. **qwen3:8b** - Good general reasoning, Apache 2.0 licensed
3. **llama3:8b** - Strong general model, Meta-trained

**Not Recommended for Deep Research:**
- Models < 7B parameters (limited reasoning depth)
- Models not trained on financial data (may miss domain-specific patterns)

### How It Works

1. **Initial Positions**: Both agents analyze the same data and provide initial recommendations
2. **Debate Rounds**: Agents take turns responding to each other's arguments
3. **Consensus Check**: After each round, the system checks if agents have reached consensus
4. **Decision**: If consensus is reached (≥80% agreement), the decision is accepted. If not after max rounds, a weighted decision is made.
5. **Logging**: All debates are logged to `data/debates.jsonl` for transparency and analysis

### Benefits

- **Reduced Bias**: Opposing perspectives balance each other out
- **Better Decisions**: Debate surfaces risks and opportunities that single-agent analysis might miss
- **Transparency**: Full debate logs show reasoning behind decisions
- **Confidence Scoring**: Consensus scores indicate decision reliability

### When to Use

- **High-stakes decisions**: Large position sizes or important portfolio changes
- **Complex situations**: When analysis is ambiguous or conflicting signals exist
- **Research mode**: For analyzing decision quality and improving prompts
- **Disabled by default**: Single-agent mode is faster and sufficient for routine decisions

## Mathematical Entry Model

Shrek buys companies only when:

1. The LLM-grounded research thesis is positive
2. The company has adequate business quality
3. Valuation offers positive expected return with margin of safety
4. Risk is acceptable
5. Technical timing is not hostile
6. The position improves the portfolio's expected risk-adjusted return

### Entry Thresholds

**Starter Buy:**
- ShrekScore >= 0.75
- Expected 12-month return >= 20%
- Upside/downside ratio >= 2.0
- Quality score >= 0.65
- Risk penalty <= 0.45
- Thesis probability >= 0.70
- Timing score >= 0.45

**Speculative Buy:**
- ShrekScore >= 0.82
- Expected 12-month return >= 30%
- Upside/downside ratio >= 3.0
- Quality score >= 0.55
- Risk penalty <= 0.55
- Thesis probability >= 0.75
- Timing score >= 0.50

## Mathematical Exit Model

Shrek sells or trims when:

1. Forward expected return collapses
2. The thesis probability drops
3. Valuation reaches fair/base value
4. Risk materially increases
5. A drawdown/trailing-stop rule triggers
6. A better opportunity dominates on risk-adjusted expected return

### Exit Thresholds

**Trim:**
- Forward expected return < 8%
- Upside/downside ratio < 1.20
- Position gain > 50% and risk increased
- Price >= base valuation

**Sell:**
- Forward expected return < 0%
- Thesis probability < 0.50
- ShrekScore < 0.55
- Risk penalty > 0.70
- Thesis-breaking event (guidance cut, margin collapse, dilution, debt crisis, regulatory issue, fraud, etc.)

## Valuation Formulas

### Scenario Valuation

For each stock, compute three deterministic valuation scenarios:

- **Bear case**: Conservative assumptions
- **Base case**: Most likely outcome
- **Bull case**: Optimistic but realistic

Each scenario uses a weighted blend of valuation methods:
- DCF (25%)
- EV/Sales (15%)
- EV/EBITDA (15%)
- P/E (15%)
- FCF yield (15%)
- Peer multiple (10%)
- Historical multiple (5%)

### DCF Formula

```
FCF_{t+1}^s = FCF_t * (1 + g_1^s)
FCF_{t+k}^s = FCF_t * product_{j=1}^{k}(1 + g_j^s)
TV_N^s = FCF_{t+N}^s * (1 + g_terminal^s) / (WACC^s - g_terminal^s)
EV_DCF^s = sum_{k=1}^{N} FCF_{t+k}^s / (1 + WACC^s)^k + TV_N^s / (1 + WACC^s)^N
EquityValue_DCF^s = EV_DCF^s + Cash - Debt - PreferredEquity - MinorityInterest
V_DCF^s = EquityValue_DCF^s / DilutedShares
```

### Expected Return

```
E[R_i] = p_i^bear * (V_i^bear / P_i - 1) + p_i^base * (V_i^base / P_i - 1) + p_i^bull * (V_i^bull / P_i - 1) + DividendYield_i
```

## Bayesian Thesis Update

Shrek uses log-odds Bayesian updating for thesis probability:

```
logit(P_i,new) = logit(P_i,old) + alpha_e * score_e * reliability_e
P_i,new = 1 / (1 + exp(-logit(P_i,new)))
```

Evidence events include:
- Earnings beat/miss with margin changes
- Guidance raises/cuts
- FCF improvement/deterioration
- Debt reduction/stress
- Dilution
- Insider buying/selling
- Accounting red flags
- Regulatory investigations
- Product traction/competitive threats

## Quality and Piotroski Scoring

### Piotroski F-Score

Nine binary signals measuring accounting quality:
- F1: ROA > 0
- F2: CFO > 0
- F3: ROA improvement
- F4: CFO > Net Income
- F5: Debt ratio improvement
- F6: Current ratio improvement
- F7: No share dilution
- F8: Gross margin improvement
- F9: Asset turnover improvement

### Business Quality Score

```
Quality_i = 0.15 * RevenueGrowthScore_i
          + 0.15 * GrossMarginScore_i
          + 0.15 * OperatingMarginScore_i
          + 0.15 * FCFMarginScore_i
          + 0.15 * ROICScore_i
          + 0.10 * BalanceSheetScore_i
          + 0.10 * PiotroskiScore_i
          + 0.05 * DilutionScore_i
```

## Risk Penalty

```
Risk_i = 0.20 * BalanceSheetRisk_i
       + 0.15 * ValuationRisk_i
       + 0.15 * DilutionRisk_i
       + 0.15 * VolatilityRisk_i
       + 0.15 * ThesisFragility_i
       + 0.10 * AccountingRisk_i
       + 0.10 * LLMRedFlagRisk_i
```

## Position Sizing

Shrek uses fractional Kelly with hard caps:

```
f_i^* = (mu_i - rf) / sigma_i^2
f_i = kelly_fraction * f_i^*
f_i,adj = f_i * P(thesis_i) * (1 - Risk_i) * min(1, UD_i / 3)
f_i,final = min(f_i,adj, max_single_position_pct)
```

Default position sizes for $100 paper account:
- Starter: 5% ($5)
- Normal: 10% ($10)
- Max conviction: 20% ($20)

## Drawdown and Trailing Stop

### Drawdown-Calibrated Stop

```
StopPrice_i = EntryPrice_i * (1 - D_i(q))
```

Where D_i(q) is the 85th percentile of historical maximum drawdown distribution.

### Trailing Stop After Large Gain

Activate trailing protection after 30% gain:

```
Trail_i = max(0.15, 2.5 * ATR20_i / Price_i)
```

Trim if trailing drawdown exceeds threshold and forward expected return < 12%.
Sell if trailing drawdown exceeds threshold and thesis probability < 60%.

## Alpaca Setup

1. Create an Alpaca paper trading account at https://alpaca.markets/
2. Obtain API key and secret key
3. Set environment variables in `.env`:
   ```
   ALPACA_API_KEY=your_key
   ALPACA_SECRET_KEY=your_secret
   ALPACA_TRADING_BASE_URL=https://paper-api.alpaca.markets
   ALPACA_DATA_BASE_URL=https://data.alpaca.markets
   ```

## SEC EDGAR Setup

1. Set your SEC user agent in `.env`:
   ```
   SEC_USER_AGENT="shrek-research/0.1 [your-email@example.com]"
   ```
2. SEC EDGAR requires a user agent string with your contact information
3. Rate limiting is enforced (10 requests/second)

## Dry-Run Mode

Dry-run mode allows testing without connecting to Alpaca:
- Set `SHREK_MODE=dry-run` in `.env`
- Orders are validated but not submitted
- Useful for testing and development

## Paper Mode

Paper mode is the default and recommended mode:
- Set `SHREK_MODE=paper` in `.env`
- Orders are submitted to Alpaca paper trading
- No real money is at risk
- Full system functionality

## Live Mode

Live mode is **explicitly disabled**:
- If `SHREK_MODE=live`, the system will exit with an error
- This is a safety constraint
- Live mode must not be implemented unless explicitly enabled by a human in the future

## Safety Constraints

Shrek enforces multiple safety constraints:

1. **Paper trading only**: live mode is disabled
2. **No shorts**: short selling is rejected
3. **No options**: options trading is rejected
4. **No market orders**: limit orders only by default
5. **No extended hours**: orders only during regular market hours
6. **No LLM-only orders**: every order must pass mathematical validation
7. **No unsupported LLM claims**: LLM outputs must cite sources
8. **No hallucinated financial data**: missing data is marked, not invented
9. **No buy without validation**: deterministic math must approve
10. **No sell without reason**: every sell must have explicit trigger
11. **Full traceability**: every order traces to decision_id and source documents
12. **Position tracking**: every position has thesis, valuation, sell triggers

## Roadmap

### Phase 1: Foundation (Complete)
- [x] Repository structure
- [x] Rust execution daemon
- [x] Python mathematical framework
- [x] Data source integrations (Alpaca, SEC EDGAR)
- [x] LLM agents (filing, earnings, valuation, risk, timing, portfolio manager)
- [x] Unit tests (Rust and Python)

### Phase 2: Research Pipeline (Complete)
- [x] SEC filing analysis
- [x] Earnings transcript processing
- [x] Memory system with layered decay
- [x] Valuation models (DCF, multiples, scenarios)
- [x] Risk scoring
- [x] Decision generation

### Phase 3: Execution (Complete)
- [x] Daily orchestration scripts
- [x] Order submission via Rust daemon
- [x] Position tracking
- [x] Portfolio optimization
- [x] Exit logic

### Phase 4: Analytics (Complete)
- [x] Backtesting system
- [x] Storage layer (DuckDB/Parquet)
- [ ] Performance reporting
- [ ] Attribution analysis
- [ ] Strategy refinement

## Installation

### Rust Dependencies

```bash
cd rust
cargo build --release
```

### Python Dependencies

```bash
cd python
pip install -e ".[dev]"
```

## Running Shrek

### Prerequisites

Run these from the repo root unless a command says otherwise.

1. Install Python dependencies:
```bash
cd python
pip install -e ".[dev]"
cd ..
```

2. Build the Rust executor:
```bash
cargo build --manifest-path rust/Cargo.toml
```

3. Set up environment variables:
```bash
cp .env.example .env
# Edit .env with your API keys
```

4. Start Ollama (if using local LLM):
```bash
ollama serve
ollama pull deepseek-r1:8b
ollama pull qwen3:8b
```

### Weekly Research And Daily Execution

This is the intended low-touch operating loop.

**Weekly research, run manually when you have time:**
```bash
./scripts/weekly_research.sh
```

This runs full research for `data/candidates.txt`, stores decisions in `data/storage/shrek_analytics.duckdb`, and writes a timestamped log under `data/logs/`.

**Daily market-hours execution, one command:**
```bash
./scripts/daily_market_execute.sh --paper
```

By default, the daily script picks a random execution time between market open and `15:30` ET, sleeps until then, starts the Rust executor if needed, and executes orders from the latest stored research. Use `--now` to execute immediately during market hours.

New buy/add orders require fresh research by default. Set `SHREK_MAX_BUY_RESEARCH_AGE_DAYS` in `.env` to control the cutoff; stale research can still trigger sell/trim exits.

Useful variants:
```bash
./scripts/daily_market_execute.sh --dry-run
./scripts/daily_market_execute.sh --paper --now
SHREK_LATEST_RANDOM_START_ET=14:45 ./scripts/daily_market_execute.sh --paper
```

### Manual Daily Workflow

Shrek is designed for manual, intermittent execution. Research can be done at any time, and trading activity is always based on the most recent research for each symbol.

**Research (run anytime - morning, afternoon, or evening):**
```bash
export PYTHONPATH="$PWD/python:${PYTHONPATH:-}"
python -m shrek_ai.scripts.manual_daily_workflow --research
```

This will:
- Research all candidates in `data/candidates.txt`
- Skip symbols already researched today (resumable)
- Generate investment decisions using multi-agent LLM analysis
- Store decisions in DuckDB database (`data/storage/shrek_analytics.duckdb`)
- **All research is persisted** in the database and available for future trading

**Execute Orders (run when you want to trade - uses latest research regardless of date):**
```bash
python -m shrek_ai.scripts.manual_daily_workflow --execute
```

This will:
- Load the **latest research decision for each symbol** (not just today)
- Calculate position sizes based on latest research
- Propose both BUY and SELL orders to Rust daemon
- Rust daemon handles order submission, fills, and risk checks

**Check Status:**
```bash
python -m shrek_ai.scripts.manual_daily_workflow --status
```

Shows:
- Latest research for each symbol (regardless of when it was done)
- Current positions
- Research database stats (total decisions, date range)

**Full Workflow (research + execute):**
```bash
python -m shrek_ai.scripts.manual_daily_workflow --full
```

### Key Features for Manual Execution

- **Research Anytime**: Run research at any point during the day
- **Latest Research Always Used**: Trading uses the most recent research per symbol, regardless of date
- **Research Database**: All research is stored in DuckDB (`data/storage/shrek_analytics.duckdb`)
- **Resumable Research**: If research is interrupted, re-running will skip already-researched symbols
- **State Persistence**: All decisions and state stored in `data/storage/`
- **Any-Time Execution**: Can start at any point during the day
- **Idempotent**: Safe to run multiple times

### Rust Execution Daemon

The Rust daemon handles:
- Order submission to Alpaca
- Order update streaming
- Position reconciliation
- Risk checks and kill switch
- Limit order management (15-minute timeout)

Start the Rust daemon (required for order execution):
```bash
cargo run --manifest-path rust/Cargo.toml -p shrek-exec -- --config config/shrek.paper.yaml --paper
```

### Additional Python Scripts

```bash
# Build universe (run periodically)
python -m shrek_ai.scripts.build_universe

# Research a single company
python -m shrek_ai.scripts.research_company AAPL

# Run daily research directly (skips already-researched symbols)
python -m shrek_ai.scripts.run_daily_research

# Backtest
python -m shrek_ai.scripts.backtest_shrek --start 2024-01-01 --end 2024-12-31 --symbols AAPL MSFT

# Post-market review
python -m shrek_ai.scripts.post_market_review
```

## Testing

### Rust Tests

```bash
cd rust
cargo test --workspace
```

### Python Tests

```bash
cd python
pytest tests/
```

## License

Proprietary - All rights reserved
