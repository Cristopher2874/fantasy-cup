#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "$0")" && pwd)"
source "${SCRIPT_DIR}/common.sh"

ensure_runtime_dirs
require_frontend_build

start_backend_background
if wait_for_backend 60; then
  echo "[backend] health check ready"
else
  echo "[backend] health check did not pass; inspect ${BACKEND_LOG_FILE}" >&2
  exit 1
fi

start_web_background
echo "[app] public bind -> http://${INNO_FANTASY_HOST}:${INNO_FANTASY_PORT}"
echo "[app] nginx route -> /edge_agentapp/"
