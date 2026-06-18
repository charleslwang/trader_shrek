#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

MODE_OVERRIDE=""
RANDOM_DELAY=1
SKIP_MARKET_HOURS_CHECK="${SKIP_MARKET_HOURS_CHECK:-0}"

usage() {
  cat <<'EOF'
Usage: ./scripts/daily_market_execute.sh [--paper|--dry-run] [--now] [--skip-market-hours-check]

Runs the daily execution workflow:
  1. Optionally waits until a random time during regular market hours.
  2. Starts the Rust execution daemon if one is not already healthy.
  3. Executes orders from the latest stored research decisions.

Defaults:
  --paper mode unless SHREK_MODE=dry-run is set
  random delay enabled; use --now to execute immediately
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --paper)
      MODE_OVERRIDE="paper"
      ;;
    --dry-run)
      MODE_OVERRIDE="dry-run"
      ;;
    --now)
      RANDOM_DELAY=0
      ;;
    --random-delay)
      RANDOM_DELAY=1
      ;;
    --skip-market-hours-check)
      SKIP_MARKET_HOURS_CHECK=1
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
  shift
done

if [[ -f "${REPO_ROOT}/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "${REPO_ROOT}/.env"
  set +a
else
  echo "Missing .env. Create it from .env.example and fill in your keys." >&2
  exit 1
fi

MODE="${MODE_OVERRIDE:-${SHREK_MODE:-paper}}"
EXECUTOR_URL="${SHREK_EXECUTOR_URL:-http://127.0.0.1:8080}"
CONFIG_PATH="${SHREK_CONFIG:-config/shrek.paper.yaml}"
LATEST_RANDOM_START_ET="${SHREK_LATEST_RANDOM_START_ET:-15:30}"

if [[ "${MODE}" != "paper" && "${MODE}" != "dry-run" ]]; then
  echo "Unsupported SHREK_MODE=${MODE}. Use paper or dry-run; live mode is disabled." >&2
  exit 1
fi

if [[ "${SKIP_MARKET_HOURS_CHECK}" != "1" ]]; then
  if [[ "${RANDOM_DELAY}" == "1" ]]; then
    DELAY_OUTPUT="$(
      python - "${LATEST_RANDOM_START_ET}" <<'PY'
from datetime import datetime, time, timedelta
from random import randint
from zoneinfo import ZoneInfo
import sys

latest_text = sys.argv[1]
latest_hour, latest_minute = [int(part) for part in latest_text.split(":", 1)]

now = datetime.now(ZoneInfo("America/New_York"))
if now.weekday() >= 5:
    print(f"Market-hours guard: today is {now:%A, %Y-%m-%d}; run this on a trading weekday.", file=sys.stderr)
    sys.exit(1)

open_at = now.replace(hour=9, minute=30, second=0, microsecond=0)
close_at = now.replace(hour=16, minute=0, second=0, microsecond=0)
latest_at = now.replace(hour=latest_hour, minute=latest_minute, second=0, microsecond=0)

if now >= close_at:
    print(f"Market-hours guard: now is {now:%Y-%m-%d %H:%M:%S %Z}; market is closed.", file=sys.stderr)
    sys.exit(1)

start_at = max(now, open_at)
end_at = min(latest_at, close_at)
if start_at >= end_at:
    target_at = start_at
else:
    window_seconds = int((end_at - start_at).total_seconds())
    target_at = start_at + timedelta(seconds=randint(0, window_seconds))

delay_seconds = max(0, int((target_at - now).total_seconds()))
print(f"{delay_seconds}|{target_at:%Y-%m-%d %H:%M:%S %Z}")
PY
    )"
    DELAY_SECONDS="${DELAY_OUTPUT%%|*}"
    TARGET_TIME="${DELAY_OUTPUT#*|}"
    echo "Daily execution target time: ${TARGET_TIME}"
    if [[ "${DELAY_SECONDS}" -gt 0 ]]; then
      echo "Sleeping for ${DELAY_SECONDS} seconds before executing."
      sleep "${DELAY_SECONDS}"
    fi
  else
    python - <<'PY'
from datetime import datetime, time
from zoneinfo import ZoneInfo
import sys

now = datetime.now(ZoneInfo("America/New_York"))
is_market_time = now.weekday() < 5 and time(9, 30) <= now.time() < time(16, 0)
if not is_market_time:
    print(
        f"Market-hours guard: now is {now:%Y-%m-%d %H:%M:%S %Z}; "
        "run during 09:30-16:00 ET or pass --skip-market-hours-check.",
        file=sys.stderr,
    )
    sys.exit(1)
PY
  fi
fi

mkdir -p "${REPO_ROOT}/data/logs"
RUN_ID="$(date +%Y%m%d_%H%M%S)"
EXEC_LOG="${REPO_ROOT}/data/logs/daily_execute_${RUN_ID}.log"
DAEMON_LOG="${REPO_ROOT}/data/logs/shrek_exec_${RUN_ID}.log"

STARTED_DAEMON=0
DAEMON_PID=""

cleanup() {
  if [[ "${STARTED_DAEMON}" == "1" && -n "${DAEMON_PID}" ]]; then
    echo "Stopping Rust execution daemon started by this script."
    kill "${DAEMON_PID}" 2>/dev/null || true
    wait "${DAEMON_PID}" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

is_healthy() {
  python - "${EXECUTOR_URL}" <<'PY' >/dev/null 2>&1
import sys
import urllib.request

base_url = sys.argv[1].rstrip("/")
try:
    with urllib.request.urlopen(f"{base_url}/health", timeout=2) as response:
        sys.exit(0 if response.status == 200 else 1)
except Exception:
    sys.exit(1)
PY
}

echo "Starting Shrek daily execution in ${MODE} mode."
echo "Execution log: ${EXEC_LOG}"

if is_healthy; then
  echo "Using existing Rust execution daemon at ${EXECUTOR_URL}."
else
  STARTED_DAEMON=1
  RUST_MODE_FLAG="--paper"
  if [[ "${MODE}" == "dry-run" ]]; then
    RUST_MODE_FLAG="--dry-run"
  fi

  echo "Starting Rust execution daemon. Daemon log: ${DAEMON_LOG}"
  (
    cd "${REPO_ROOT}"
    cargo run --manifest-path rust/Cargo.toml -p shrek-exec -- --config "${CONFIG_PATH}" "${RUST_MODE_FLAG}"
  ) >"${DAEMON_LOG}" 2>&1 &
  DAEMON_PID="$!"

  for _ in {1..60}; do
    if is_healthy; then
      break
    fi
    if ! kill -0 "${DAEMON_PID}" 2>/dev/null; then
      echo "Rust execution daemon exited before becoming healthy." >&2
      tail -80 "${DAEMON_LOG}" >&2 || true
      exit 1
    fi
    sleep 1
  done

  if ! is_healthy; then
    echo "Rust execution daemon did not become healthy within 60 seconds." >&2
    tail -80 "${DAEMON_LOG}" >&2 || true
    exit 1
  fi
fi

cd "${REPO_ROOT}"
export PYTHONPATH="${REPO_ROOT}/python:${PYTHONPATH:-}"
python -m shrek_ai.scripts.manual_daily_workflow --execute 2>&1 | tee "${EXEC_LOG}"

echo "Daily execution complete."
