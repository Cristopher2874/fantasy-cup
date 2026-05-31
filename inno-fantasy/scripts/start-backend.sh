#!/usr/bin/env bash
set -euo pipefail

# Preferred VM entrypoint for the FastAPI backend.
#
# Usage:
#   bash scripts/start-backend.sh
#
# Optional environment knobs:
#   BACKEND_HOST=127.0.0.1
#   BACKEND_PORT=10006
#   FORWARDED_ALLOW_IPS=127.0.0.1
#   LOG_LEVEL=info
#   BACKEND_RELOAD=1                 # local/dev only
#   BACKEND_WORKERS=1                # keep 1 for the current MVP
#   ALLOW_MULTIPLE_WORKERS=1         # bypass worker guard if a shared job store is added later

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
APP_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
BACKEND_DIR="${APP_ROOT}/backend"

HOST="${BACKEND_HOST:-127.0.0.1}"
PORT="${BACKEND_PORT:-10006}"
FORWARDED_ALLOW_IPS="${FORWARDED_ALLOW_IPS:-127.0.0.1}"
LOG_LEVEL="${LOG_LEVEL:-info}"
WORKERS="${BACKEND_WORKERS:-1}"

if [[ "${WORKERS}" != "1" && "${ALLOW_MULTIPLE_WORKERS:-0}" != "1" ]]; then
  echo "Refusing to start with BACKEND_WORKERS=${WORKERS}." >&2
  echo "This MVP keeps pipeline progress in process memory; use one worker unless a shared job store is added." >&2
  exit 2
fi

if [[ ! -f "${BACKEND_DIR}/.env" ]]; then
  echo "[backend] warning: ${BACKEND_DIR}/.env was not found. The app can still start if secrets are provided by the VM environment." >&2
fi

cmd=(
  uv run uvicorn main:app
  --host "${HOST}"
  --port "${PORT}"
  --proxy-headers
  --forwarded-allow-ips "${FORWARDED_ALLOW_IPS}"
  --log-level "${LOG_LEVEL}"
)

if [[ "${BACKEND_RELOAD:-0}" == "1" ]]; then
  cmd+=(--reload)
elif [[ "${WORKERS}" != "1" ]]; then
  cmd+=(--workers "${WORKERS}")
fi

cd "${BACKEND_DIR}"

echo "[backend] starting host=${HOST} port=${PORT} forwarded_allow_ips=${FORWARDED_ALLOW_IPS} workers=${WORKERS}"
exec "${cmd[@]}"
