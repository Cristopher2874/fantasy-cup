#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/common.sh"

ensure_runtime_dirs
require_truth_file

if [[ -f "$PID_FILE" ]]; then
  pid="$(cat "$PID_FILE" 2>/dev/null || true)"
  if [[ -n "${pid:-}" ]] && is_pid_running "$pid"; then
    echo "playtest: already running (PID $pid)"
    exit 0
  fi
  rm -f "$PID_FILE"
fi

(
  cd "$PROJECT_ROOT"
  exec_python -u playtest_app/server.py --host "$PLAYTEST_HOST" --port "$PLAYTEST_PORT"
) >>"$LOG_FILE" 2>&1 &
server_pid=$!
echo "$server_pid" >"$PID_FILE"

echo "playtest: started PID $server_pid on $PLAYTEST_HOST:$PLAYTEST_PORT"
echo "playtest: log -> $LOG_FILE"
