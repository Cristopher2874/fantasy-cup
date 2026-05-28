#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/common.sh"

stop_from_pid_file "$CLIENT_PID_FILE" "client"

if command -v pgrep >/dev/null 2>&1; then
  pids="$(pgrep -f "http\.server[[:space:]]+$CLIENT_PORT" || true)"
  if [[ -n "${pids:-}" ]]; then
    echo "client: fallback stop for matching process IDs: $pids"
    kill $pids || true
  fi
fi
