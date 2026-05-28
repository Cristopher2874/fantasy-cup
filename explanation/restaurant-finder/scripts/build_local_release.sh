#!/usr/bin/env bash
set -euo pipefail

# Build artifacts on a machine with npm, then package for VM deployment.

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/common.sh"

RELEASE_DIR="${RELEASE_DIR:-$PROJECT_ROOT/release}"
CLIENT_RELEASE_DIR="$RELEASE_DIR/${APP_NAME}-client-dist"
CLIENT_TARBALL="$RELEASE_DIR/${APP_NAME}-client-dist.tar.gz"

echo "release: cleaning old artifacts"
rm -rf "$CLIENT_RELEASE_DIR"
mkdir -p "$CLIENT_RELEASE_DIR"

echo "release: building renderers/web_core"
(
  cd "$PROJECT_ROOT/renderers/web_core"
  npm ci
  npm run build
)

echo "release: building renderers/lit"
(
  cd "$PROJECT_ROOT/renderers/lit"
  npm ci
  npm run build
)

echo "release: installing app/client workspace deps"
(
  cd "$PROJECT_ROOT/app/client"
  npm ci
)

echo "release: building production client bundle for /edge_agentapp/"
(
  cd "$PROJECT_ROOT/app/client/shell"
  # Prevent Git Bash (MSYS) from rewriting /edge_agentapp/* into Windows paths.
  MSYS_NO_PATHCONV=1 \
  MSYS2_ARG_CONV_EXCL="*" \
  VITE_PUBLIC_BASE_PATH="/edge_agentapp/" \
  VITE_AGENT_SERVER_URL="/edge_agentapp/api/agent" \
  VITE_AGENT_CONFIG_URL="/edge_agentapp/api/agent/config" \
  npm run build:deploy
)

cp -R "$PROJECT_ROOT/app/client/shell/dist/." "$CLIENT_RELEASE_DIR/"

tar -czf "$CLIENT_TARBALL" -C "$CLIENT_RELEASE_DIR" .

cat <<EOF
release: complete
- Bundle directory: $CLIENT_RELEASE_DIR
- Tarball: $CLIENT_TARBALL

VM usage:
1) Copy '$CLIENT_TARBALL' to the VM.
2) Extract to a directory, for example:
   mkdir -p /opt/${APP_NAME}/dist
   tar -xzf ${APP_NAME}-client-dist.tar.gz -C /opt/${APP_NAME}/dist
3) Start services with:
   CLIENT_DIST_DIR=/opt/${APP_NAME}/dist SERVER_PORT=${SERVER_PORT} CLIENT_PORT=${CLIENT_PORT} ./scripts/start_all.sh
EOF
