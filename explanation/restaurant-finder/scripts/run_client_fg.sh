#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/common.sh"

if [[ ! -d "$CLIENT_DIST_DIR" ]]; then
  echo "client: dist not found at $CLIENT_DIST_DIR"
  echo "client: build locally first (see scripts/build_local_release.sh)"
  exit 1
fi

python_cmd="$(pick_python_cmd || true)"
if [[ -z "${python_cmd:-}" ]]; then
  echo "client: python not found (need python3 or python)"
  exit 1
fi

cd "$PROJECT_ROOT"
exec "$python_cmd" -m http.server "$CLIENT_PORT" --bind "$CLIENT_HOST" --directory "$CLIENT_DIST_DIR"
