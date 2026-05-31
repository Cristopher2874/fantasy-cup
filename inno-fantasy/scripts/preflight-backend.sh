#!/usr/bin/env bash
set -euo pipefail

# Deployment preflight for the backend VM.
#
# Usage:
#   bash scripts/preflight-backend.sh
#
# This checks local prerequisites only; it does not call API-Football, OCI, or
# Codex with real work.

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
APP_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
BACKEND_DIR="${APP_ROOT}/backend"

failures=0

check_ok() {
  echo "[ok] $1"
}

check_warn() {
  echo "[warn] $1" >&2
}

check_fail() {
  echo "[fail] $1" >&2
  failures=$((failures + 1))
}

if command -v uv >/dev/null 2>&1; then
  check_ok "uv is available: $(command -v uv)"
else
  check_fail "uv is not available on PATH"
fi

if [[ -f "${BACKEND_DIR}/.env" ]]; then
  check_ok "backend .env exists"
else
  check_fail "backend .env is missing; copy backend/.env.example to backend/.env and fill VM values"
fi

if [[ -f "${BACKEND_DIR}/config/config.yaml" ]]; then
  check_ok "backend config exists"
else
  check_fail "backend config/config.yaml is missing"
fi

if [[ -d "${BACKEND_DIR}/.venv" ]]; then
  check_ok "backend .venv exists"
else
  check_warn "backend .venv does not exist yet; uv will create/use an environment on first run"
fi

if command -v uv >/dev/null 2>&1; then
  if (
    cd "${BACKEND_DIR}"
    uv run python -c "import main; print('routes', len(main.app.routes))" >/tmp/inno-fantasy-preflight-import.txt
  ); then
    check_ok "backend imports successfully ($(cat /tmp/inno-fantasy-preflight-import.txt))"
  else
    check_fail "backend import check failed"
  fi

  if CODEX_COMMAND="$(
    cd "${BACKEND_DIR}"
    uv run python -c "from config.config_provider import GlobalConfigProvider; print(GlobalConfigProvider().get_str('codex_runner','command','codex'))"
  )"; then
    if [[ "${CODEX_COMMAND}" == */* ]]; then
      if [[ -x "${CODEX_COMMAND}" ]]; then
        check_ok "Codex command is executable: ${CODEX_COMMAND}"
      else
        check_fail "Codex command path is not executable: ${CODEX_COMMAND}"
      fi
    elif command -v "${CODEX_COMMAND}" >/dev/null 2>&1; then
      check_ok "Codex command is on PATH: $(command -v "${CODEX_COMMAND}")"
    else
      check_fail "Codex command is not available on PATH: ${CODEX_COMMAND}"
    fi
  else
    check_fail "Could not read codex_runner.command from config"
  fi

  if (
    cd "${BACKEND_DIR}"
    uv run python -c "from services.data_generator.public_data import resolve_api_key; raise SystemExit(0 if resolve_api_key() else 1)"
  ); then
    check_ok "API-Football key is configured"
  else
    check_fail "API-Football key is missing; set APISPORTS_KEY or API_FOOTBALL_KEY"
  fi

  if (
    cd "${BACKEND_DIR}"
    uv run python -c "from config.config_provider import GlobalConfigProvider; c=GlobalConfigProvider(); raise SystemExit(0 if c.get_config_value('oci','compartment') and c.get_config_value('oci','project') else 1)"
  ); then
    check_ok "OCI compartment/project values are configured"
  else
    check_fail "OCI compartment/project values are missing; set OCI_COMPARTMENT_OCID and OCI_PROJECT"
  fi
fi

if [[ -d "${APP_ROOT}/data/public_data" ]]; then
  check_ok "public data directory exists"
else
  check_warn "public data has not been generated yet; run bash scripts/generate-game-data.sh public YYYY-MM-DD"
fi

if [[ -d "${APP_ROOT}/data/source_of_truth" ]]; then
  check_ok "source-of-truth directory exists"
else
  check_warn "source of truth has not been generated yet; run bash scripts/generate-game-data.sh truth YYYY-MM-DD after matches finish"
fi

if [[ "${failures}" -gt 0 ]]; then
  echo "[preflight] failed with ${failures} issue(s)" >&2
  exit 1
fi

echo "[preflight] ready"
