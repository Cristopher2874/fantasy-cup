#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "$0")" && pwd)"
source "${SCRIPT_DIR}/common.sh"

stop_pid_file "[web]" "${WEB_PID_FILE}"
stop_pid_file "[backend]" "${BACKEND_PID_FILE}"
