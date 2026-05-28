#!/usr/bin/env bash
set -euo pipefail

# Full reset cycle:
# 1) stop both
# 2) clear stale pid files
# 3) start both

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/common.sh"

"$SCRIPT_DIR/stop_all.sh"
rm -f "$SERVER_PID_FILE" "$CLIENT_PID_FILE"
"$SCRIPT_DIR/start_all.sh"

echo "Reset complete."
