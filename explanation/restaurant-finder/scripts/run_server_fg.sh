#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/common.sh"

cd "$SERVER_DIR"
exec uv run __main__.py --host "$SERVER_HOST" --port "$SERVER_PORT"
