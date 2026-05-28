#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/common.sh"

if [[ ! -f "$PID_FILE" ]]; then
  echo "playtest: PID file not found ($PID_FILE)"
  exit 0
fi

pid="$(cat "$PID_FILE" 2>/dev/null || true)"
if [[ -z "${pid:-}" ]]; then
  echo "playtest: PID file is empty, removing stale file"
  rm -f "$PID_FILE"
  exit 0
fi

if is_pid_running "$pid"; then
  echo "playtest: stopping PID $pid"
  kill "$pid" || true
  sleep 1
  if is_pid_running "$pid"; then
    echo "playtest: PID $pid still running, sending SIGKILL"
    kill -9 "$pid" || true
  fi
else
  echo "playtest: PID $pid is not running"
fi

rm -f "$PID_FILE"
