#!/usr/bin/env bash
set -euo pipefail

# Starts both services in background (client then server).

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
"$SCRIPT_DIR/start_client_bg.sh"
"$SCRIPT_DIR/start_server_bg.sh"

echo "Both services requested."
