#!/usr/bin/env bash
set -euo pipefail

# Stops both services.

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
"$SCRIPT_DIR/stop_server.sh"
"$SCRIPT_DIR/stop_client.sh"

echo "Both services stop complete."
