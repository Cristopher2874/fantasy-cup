#!/usr/bin/env bash
set -euo pipefail

# Shared paths and helpers for local VM process control.
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")"/.. && pwd)"
RUN_DIR="$PROJECT_ROOT/run"
LOG_DIR="$PROJECT_ROOT/logs"

APP_NAME="${APP_NAME:-edge-agentapp}"
SERVER_HOST="${SERVER_HOST:-127.0.0.1}"
CLIENT_HOST="${CLIENT_HOST:-127.0.0.1}"

# Restaurant Finder VM defaults
SERVER_PORT="${SERVER_PORT:-10004}"
CLIENT_PORT="${CLIENT_PORT:-6004}"

SERVER_PID_FILE="$RUN_DIR/${APP_NAME}-api-${SERVER_PORT}.pid"
CLIENT_PID_FILE="$RUN_DIR/${APP_NAME}-client-${CLIENT_PORT}.pid"

SERVER_LOG_FILE="$LOG_DIR/${APP_NAME}-api-${SERVER_PORT}.out"
CLIENT_LOG_FILE="$LOG_DIR/${APP_NAME}-client-${CLIENT_PORT}.out"

SERVER_DIR="$PROJECT_ROOT/app/server"

# Client build location precedence:
# 1) explicit CLIENT_DIST_DIR env var
# 2) repo-level dist_web (VM extracted bundle)
# 3) local shell dist (developer machine build output)
if [[ -z "${CLIENT_DIST_DIR:-}" ]]; then
  if [[ -d "$PROJECT_ROOT/dist_web" ]]; then
    CLIENT_DIST_DIR="$PROJECT_ROOT/dist_web"
  else
    CLIENT_DIST_DIR="$PROJECT_ROOT/app/client/shell/dist"
  fi
fi

ensure_runtime_dirs() {
  mkdir -p "$RUN_DIR" "$LOG_DIR"
}

is_pid_running() {
  local pid="$1"
  kill -0 "$pid" 2>/dev/null
}

stop_from_pid_file() {
  local pid_file="$1"
  local label="$2"

  if [[ ! -f "$pid_file" ]]; then
    echo "$label: PID file not found ($pid_file)"
    return 0
  fi

  local pid
  pid="$(cat "$pid_file" 2>/dev/null || true)"
  if [[ -z "$pid" ]]; then
    echo "$label: PID file is empty, removing stale file"
    rm -f "$pid_file"
    return 0
  fi

  if is_pid_running "$pid"; then
    echo "$label: stopping PID $pid"
    kill "$pid" || true
    sleep 1
    if is_pid_running "$pid"; then
      echo "$label: PID $pid still running, sending SIGKILL"
      kill -9 "$pid" || true
    fi
  else
    echo "$label: PID $pid is not running"
  fi

  rm -f "$pid_file"
}

pick_python_cmd() {
  if command -v python3 >/dev/null 2>&1; then
    echo "python3"
    return 0
  fi

  if command -v python >/dev/null 2>&1; then
    echo "python"
    return 0
  fi

  return 1
}
