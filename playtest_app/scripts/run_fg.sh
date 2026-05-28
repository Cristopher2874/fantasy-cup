#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/common.sh"

ensure_runtime_dirs
require_truth_file

PYTHON_CMD="$(pick_python_cmd)"
cd "$PROJECT_ROOT"
exec "$PYTHON_CMD" -u playtest_app/server.py --host "$PLAYTEST_HOST" --port "$PLAYTEST_PORT"
