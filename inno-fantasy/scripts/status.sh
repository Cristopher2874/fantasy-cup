#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "$0")" && pwd)"
source "${SCRIPT_DIR}/common.sh"

print_status "[backend]" "${BACKEND_PID_FILE}" "${BACKEND_HOST}" "${BACKEND_PORT}" "${BACKEND_LOG_FILE}"
print_status "[web]" "${WEB_PID_FILE}" "${INNO_FANTASY_HOST}" "${INNO_FANTASY_PORT}" "${WEB_LOG_FILE}"
