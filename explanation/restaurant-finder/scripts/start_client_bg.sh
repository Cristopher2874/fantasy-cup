#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/common.sh"

ensure_runtime_dirs

if [[ ! -d "$CLIENT_DIST_DIR" ]]; then
  echo "client: dist not found at $CLIENT_DIST_DIR"
  echo "client: build locally first (see scripts/build_local_release.sh)"
  exit 1
fi

if [[ -f "$CLIENT_PID_FILE" ]]; then
  pid="$(cat "$CLIENT_PID_FILE" 2>/dev/null || true)"
  if [[ -n "${pid:-}" ]] && is_pid_running "$pid"; then
    echo "client: already running (PID $pid)"
    exit 0
  fi
  rm -f "$CLIENT_PID_FILE"
fi

python_cmd="$(pick_python_cmd || true)"
if [[ -z "${python_cmd:-}" ]]; then
  echo "client: python not found (need python3 or python)"
  exit 1
fi

cd "$PROJECT_ROOT"
nohup "$python_cmd" -m http.server "$CLIENT_PORT" --bind "$CLIENT_HOST" --directory "$CLIENT_DIST_DIR" >>"$CLIENT_LOG_FILE" 2>&1 &
client_pid=$!
echo "$client_pid" >"$CLIENT_PID_FILE"

echo "client: started PID $client_pid on $CLIENT_HOST:$CLIENT_PORT"
echo "client: serving $CLIENT_DIST_DIR"
echo "client: log -> $CLIENT_LOG_FILE"
