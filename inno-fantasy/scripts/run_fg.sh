#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "$0")" && pwd)"
source "${SCRIPT_DIR}/common.sh"

ensure_runtime_dirs
require_frontend_build

started_backend=0

cleanup() {
  if [[ "${started_backend}" == "1" ]]; then
    stop_pid_file "[backend]" "${BACKEND_PID_FILE}"
  fi
}

trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

remove_stale_pid_file "${BACKEND_PID_FILE}"
if pid_file_is_running "${BACKEND_PID_FILE}"; then
  echo "[backend] using existing PID $(pid_from_file "${BACKEND_PID_FILE}") on ${BACKEND_HOST}:${BACKEND_PORT}"
else
  start_backend_background
  started_backend=1
fi

if wait_for_backend 60; then
  echo "[backend] health check ready"
else
  echo "[backend] health check did not pass; inspect ${BACKEND_LOG_FILE}" >&2
  exit 1
fi

echo "[web] starting foreground server on ${INNO_FANTASY_HOST}:${INNO_FANTASY_PORT}"
echo "[web] proxying API routes to ${INNO_FANTASY_BACKEND_URL}"
(
  exec_web
)
