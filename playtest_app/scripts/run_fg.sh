#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/common.sh"

ensure_runtime_dirs
require_truth_file

cd "$PROJECT_ROOT"
exec_python -u playtest_app/server.py --host "$PLAYTEST_HOST" --port "$PLAYTEST_PORT"
