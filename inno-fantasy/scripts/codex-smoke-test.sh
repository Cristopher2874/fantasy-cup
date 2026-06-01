#!/usr/bin/env bash
set -euo pipefail

# Verifies that the VM user can run the same Codex CLI shape used by the backend
# skill runner. This makes a small real Codex request.
#
# Usage:
#   bash scripts/codex-smoke-test.sh
#
# Optional environment knobs:
#   CODEX_COMMAND=codex
#   CODEX_SANDBOX=read-only
#   CODEX_ENABLE_SEARCH=1
#   CODEX_SKIP_GIT_REPO_CHECK=1

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
APP_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"

CODEX_COMMAND="${CODEX_COMMAND:-codex}"
CODEX_SANDBOX="${CODEX_SANDBOX:-read-only}"
CODEX_ENABLE_SEARCH="${CODEX_ENABLE_SEARCH:-1}"
CODEX_SKIP_GIT_REPO_CHECK="${CODEX_SKIP_GIT_REPO_CHECK:-1}"

if ! command -v "${CODEX_COMMAND}" >/dev/null 2>&1; then
  echo "[fail] Codex command is not on PATH: ${CODEX_COMMAND}" >&2
  echo "Install Codex CLI or set CODEX_COMMAND=/absolute/path/to/codex" >&2
  exit 1
fi

echo "[ok] codex command: $(command -v "${CODEX_COMMAND}")"
"${CODEX_COMMAND}" --version

output_dir="${APP_ROOT}/data/codex_smoke"
mkdir -p "${output_dir}"
output_file="${output_dir}/codex.final-message.txt"
stdout_file="${output_dir}/codex.stdout.log"
stderr_file="${output_dir}/codex.stderr.log"

cmd=(
  "${CODEX_COMMAND}"
  --sandbox "${CODEX_SANDBOX}"
)

if [[ "${CODEX_ENABLE_SEARCH}" == "1" ]]; then
  cmd+=(--search)
fi

cmd+=(exec)

if [[ "${CODEX_SKIP_GIT_REPO_CHECK}" == "1" ]]; then
  cmd+=(--skip-git-repo-check)
fi

cmd+=(--output-last-message "${output_file}" -)

prompt='Return exactly {"ok": true, "source": "codex-smoke-test"} and no markdown.'

echo "[smoke] running: ${cmd[*]}"
if printf '%s\n' "${prompt}" | "${cmd[@]}" >"${stdout_file}" 2>"${stderr_file}"; then
  echo "[ok] Codex exec completed"
  echo "[ok] final message -> ${output_file}"
  cat "${output_file}"
else
  status=$?
  echo "[fail] Codex exec failed with status ${status}" >&2
  echo "[fail] stdout -> ${stdout_file}" >&2
  echo "[fail] stderr -> ${stderr_file}" >&2
  tail -n 80 "${stderr_file}" >&2 || true
  exit "${status}"
fi
