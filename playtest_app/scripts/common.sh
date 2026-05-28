#!/usr/bin/env bash
set -euo pipefail

APP_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")"/.. && pwd)"
PROJECT_ROOT="$(cd "$APP_ROOT"/.. && pwd)"
RUN_DIR="$APP_ROOT/run"
LOG_DIR="$APP_ROOT/logs"

APP_NAME="${APP_NAME:-edge-agentapp}"
PLAYTEST_HOST="${PLAYTEST_HOST:-127.0.0.1}"
PLAYTEST_PORT="${PLAYTEST_PORT:-6004}"

PID_FILE="$RUN_DIR/${APP_NAME}-${PLAYTEST_PORT}.pid"
LOG_FILE="$LOG_DIR/${APP_NAME}-${PLAYTEST_PORT}.out"

ensure_runtime_dirs() {
  mkdir -p "$RUN_DIR" "$LOG_DIR" "$APP_ROOT/data"
}

is_pid_running() {
  local pid="$1"
  kill -0 "$pid" 2>/dev/null
}

pick_python_cmd() {
  if [[ -x "$PROJECT_ROOT/.venv/bin/python" ]]; then
    echo "$PROJECT_ROOT/.venv/bin/python"
    return 0
  fi

  if command -v python3 >/dev/null 2>&1; then
    echo "python3"
    return 0
  fi

  if command -v python >/dev/null 2>&1; then
    echo "python"
    return 0
  fi

  echo "python runtime not found" >&2
  return 1
}

require_truth_file() {
  local truth_file="$PROJECT_ROOT/scoring/truth_data/latest_truth.json"
  if [[ ! -f "$truth_file" ]]; then
    echo "missing truth file: $truth_file" >&2
    echo "copy it to the VM or run scoring/daily_truth_pipeline.py before starting" >&2
    return 1
  fi
}
