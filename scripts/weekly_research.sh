#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

if [[ -f "${REPO_ROOT}/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "${REPO_ROOT}/.env"
  set +a
else
  echo "Missing .env. Create it from .env.example and fill in your keys." >&2
  exit 1
fi

mkdir -p "${REPO_ROOT}/data/logs"
LOG_FILE="${REPO_ROOT}/data/logs/weekly_research_$(date +%Y%m%d_%H%M%S).log"

echo "Starting weekly Shrek research."
echo "Log: ${LOG_FILE}"

cd "${REPO_ROOT}"
export PYTHONPATH="${REPO_ROOT}/python:${PYTHONPATH:-}"
python -m shrek_ai.scripts.manual_daily_workflow --research 2>&1 | tee "${LOG_FILE}"

echo "Weekly research complete."
