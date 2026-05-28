#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/common.sh"

if [[ ! -f "$PID_FILE" ]]; then
  echo "playtest: stopped"
  exit 0
fi

pid="$(cat "$PID_FILE" 2>/dev/null || true)"
if [[ -n "${pid:-}" ]] && is_pid_running "$pid"; then
  echo "playtest: running PID $pid on $PLAYTEST_HOST:$PLAYTEST_PORT"
  echo "playtest: log -> $LOG_FILE"
else
  echo "playtest: stale PID file ($PID_FILE)"
fi
