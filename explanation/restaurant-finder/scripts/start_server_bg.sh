#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/common.sh"

ensure_runtime_dirs

if [[ -f "$SERVER_PID_FILE" ]]; then
  pid="$(cat "$SERVER_PID_FILE" 2>/dev/null || true)"
  if [[ -n "${pid:-}" ]] && is_pid_running "$pid"; then
    echo "server: already running (PID $pid)"
    exit 0
  fi
  rm -f "$SERVER_PID_FILE"
fi

cd "$SERVER_DIR"
nohup uv run __main__.py --host "$SERVER_HOST" --port "$SERVER_PORT" >>"$SERVER_LOG_FILE" 2>&1 &
server_pid=$!
echo "$server_pid" >"$SERVER_PID_FILE"

echo "server: started PID $server_pid on $SERVER_HOST:$SERVER_PORT"
echo "server: log -> $SERVER_LOG_FILE"
