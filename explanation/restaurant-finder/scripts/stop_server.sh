#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/common.sh"

stop_from_pid_file "$SERVER_PID_FILE" "server"

if command -v pgrep >/dev/null 2>&1; then
  pids="$(pgrep -f "__main__\.py.*--port[[:space:]]*$SERVER_PORT|__main__\.py" || true)"
  if [[ -n "${pids:-}" ]]; then
    echo "server: fallback stop for matching process IDs: $pids"
    kill $pids || true
  fi
fi
