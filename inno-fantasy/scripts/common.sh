#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
APP_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
BACKEND_DIR="${APP_ROOT}/backend"
RUN_DIR="${APP_ROOT}/run"
LOG_DIR="${APP_ROOT}/logs"

APP_NAME="${APP_NAME:-edge-agentapp}"
INNO_FANTASY_HOST="${INNO_FANTASY_HOST:-${APP_HOST:-127.0.0.1}}"
INNO_FANTASY_PORT="${INNO_FANTASY_PORT:-${APP_PORT:-6004}}"
BACKEND_HOST="${BACKEND_HOST:-127.0.0.1}"
BACKEND_PORT="${BACKEND_PORT:-10006}"
FORWARDED_ALLOW_IPS="${FORWARDED_ALLOW_IPS:-127.0.0.1}"
LOG_LEVEL="${LOG_LEVEL:-info}"
BACKEND_WORKERS="${BACKEND_WORKERS:-1}"
FRONTEND_BUILD_DIR="${FRONTEND_BUILD_DIR:-${APP_ROOT}/frontend/inno-fantasy/build}"
INNO_FANTASY_BACKEND_URL="${INNO_FANTASY_BACKEND_URL:-http://${BACKEND_HOST}:${BACKEND_PORT}}"

WEB_PID_FILE="${RUN_DIR}/${APP_NAME}-web-${INNO_FANTASY_PORT}.pid"
BACKEND_PID_FILE="${RUN_DIR}/${APP_NAME}-backend-${BACKEND_PORT}.pid"
WEB_LOG_FILE="${LOG_DIR}/${APP_NAME}-web-${INNO_FANTASY_PORT}.out"
BACKEND_LOG_FILE="${LOG_DIR}/${APP_NAME}-backend-${BACKEND_PORT}.out"

ensure_runtime_dirs() {
  mkdir -p "${RUN_DIR}" "${LOG_DIR}"
}

is_pid_running() {
  local pid="$1"
  kill -0 "${pid}" 2>/dev/null
}

pid_from_file() {
  local pid_file="$1"
  if [[ -f "${pid_file}" ]]; then
    cat "${pid_file}" 2>/dev/null || true
  fi
}

pid_file_is_running() {
  local pid_file="$1"
  local pid
  pid="$(pid_from_file "${pid_file}")"
  [[ -n "${pid:-}" ]] && is_pid_running "${pid}"
}

remove_stale_pid_file() {
  local pid_file="$1"
  if [[ -f "${pid_file}" ]] && ! pid_file_is_running "${pid_file}"; then
    rm -f "${pid_file}"
  fi
}

python_command() {
  if command -v python3 >/dev/null 2>&1; then
    command -v python3
    return 0
  fi

  if command -v python >/dev/null 2>&1; then
    command -v python
    return 0
  fi

  echo "python runtime not found; install uv or python3" >&2
  return 1
}

require_frontend_build() {
  if [[ -f "${FRONTEND_BUILD_DIR}/index.html" ]]; then
    return 0
  fi

  echo "missing frontend build: ${FRONTEND_BUILD_DIR}/index.html" >&2
  echo "build locally with npm, then copy frontend/inno-fantasy/build to the VM" >&2
  return 1
}

ensure_backend_worker_mode() {
  if [[ "${BACKEND_WORKERS}" != "1" && "${ALLOW_MULTIPLE_WORKERS:-0}" != "1" ]]; then
    echo "Refusing BACKEND_WORKERS=${BACKEND_WORKERS}; progress state is in-process for the MVP." >&2
    echo "Set ALLOW_MULTIPLE_WORKERS=1 only after adding a shared job store." >&2
    return 2
  fi
}

exec_backend() {
  ensure_backend_worker_mode

  if [[ ! -f "${BACKEND_DIR}/.env" ]]; then
    echo "[backend] warning: ${BACKEND_DIR}/.env was not found. VM environment variables may still provide secrets." >&2
  fi

  local cmd=(
    uv run uvicorn main:app
    --host "${BACKEND_HOST}"
    --port "${BACKEND_PORT}"
    --proxy-headers
    --forwarded-allow-ips "${FORWARDED_ALLOW_IPS}"
    --log-level "${LOG_LEVEL}"
  )

  if [[ "${BACKEND_RELOAD:-0}" == "1" ]]; then
    cmd+=(--reload)
  elif [[ "${BACKEND_WORKERS}" != "1" ]]; then
    cmd+=(--workers "${BACKEND_WORKERS}")
  fi

  cd "${BACKEND_DIR}"
  if command -v uv >/dev/null 2>&1; then
    exec "${cmd[@]}"
  fi

  local python_bin
  python_bin="$(python_command)"
  exec "${python_bin}" -m uvicorn main:app \
    --host "${BACKEND_HOST}" \
    --port "${BACKEND_PORT}" \
    --proxy-headers \
    --forwarded-allow-ips "${FORWARDED_ALLOW_IPS}" \
    --log-level "${LOG_LEVEL}"
}

exec_web() {
  cd "${APP_ROOT}"

  if command -v uv >/dev/null 2>&1; then
    exec uv run --no-project python -u server.py \
      --host "${INNO_FANTASY_HOST}" \
      --port "${INNO_FANTASY_PORT}" \
      --backend-url "${INNO_FANTASY_BACKEND_URL}" \
      --build-dir "${FRONTEND_BUILD_DIR}"
  fi

  local python_bin
  python_bin="$(python_command)"
  exec "${python_bin}" -u server.py \
    --host "${INNO_FANTASY_HOST}" \
    --port "${INNO_FANTASY_PORT}" \
    --backend-url "${INNO_FANTASY_BACKEND_URL}" \
    --build-dir "${FRONTEND_BUILD_DIR}"
}

wait_for_backend() {
  local attempts="${1:-60}"
  local python_bin
  python_bin="$(python_command)"

  for _ in $(seq 1 "${attempts}"); do
    if "${python_bin}" -c "import sys, urllib.request; urllib.request.urlopen(sys.argv[1], timeout=1).read()" "${INNO_FANTASY_BACKEND_URL}/health" >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done

  return 1
}

start_backend_background() {
  remove_stale_pid_file "${BACKEND_PID_FILE}"
  if pid_file_is_running "${BACKEND_PID_FILE}"; then
    echo "[backend] already running PID $(pid_from_file "${BACKEND_PID_FILE}") on ${BACKEND_HOST}:${BACKEND_PORT}"
    return 0
  fi

  (
    exec_backend
  ) >>"${BACKEND_LOG_FILE}" 2>&1 &
  local pid=$!
  echo "${pid}" >"${BACKEND_PID_FILE}"

  echo "[backend] started PID ${pid} on ${BACKEND_HOST}:${BACKEND_PORT}"
  echo "[backend] log -> ${BACKEND_LOG_FILE}"
}

start_web_background() {
  remove_stale_pid_file "${WEB_PID_FILE}"
  if pid_file_is_running "${WEB_PID_FILE}"; then
    echo "[web] already running PID $(pid_from_file "${WEB_PID_FILE}") on ${INNO_FANTASY_HOST}:${INNO_FANTASY_PORT}"
    return 0
  fi

  (
    exec_web
  ) >>"${WEB_LOG_FILE}" 2>&1 &
  local pid=$!
  echo "${pid}" >"${WEB_PID_FILE}"

  echo "[web] started PID ${pid} on ${INNO_FANTASY_HOST}:${INNO_FANTASY_PORT}"
  echo "[web] log -> ${WEB_LOG_FILE}"
}

stop_pid_file() {
  local label="$1"
  local pid_file="$2"

  if [[ ! -f "${pid_file}" ]]; then
    echo "${label}: stopped"
    return 0
  fi

  local pid
  pid="$(pid_from_file "${pid_file}")"
  if [[ -z "${pid:-}" ]]; then
    echo "${label}: PID file is empty, removing stale file"
    rm -f "${pid_file}"
    return 0
  fi

  if is_pid_running "${pid}"; then
    echo "${label}: stopping PID ${pid}"
    kill "${pid}" || true
    sleep 1
    if is_pid_running "${pid}"; then
      echo "${label}: PID ${pid} still running, sending SIGKILL"
      kill -9 "${pid}" || true
    fi
  else
    echo "${label}: PID ${pid} is not running"
  fi

  rm -f "${pid_file}"
}

print_status() {
  local label="$1"
  local pid_file="$2"
  local host="$3"
  local port="$4"
  local log_file="$5"

  if pid_file_is_running "${pid_file}"; then
    echo "${label}: running PID $(pid_from_file "${pid_file}") on ${host}:${port}"
    echo "${label}: log -> ${log_file}"
    return 0
  fi

  if [[ -f "${pid_file}" ]]; then
    echo "${label}: stale PID file (${pid_file})"
    return 0
  fi

  echo "${label}: stopped"
}
