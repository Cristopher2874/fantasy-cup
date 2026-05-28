#!/usr/bin/env bash
set -euo pipefail

# Starts both services and performs lightweight health checks.

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/common.sh"

"$SCRIPT_DIR/start_all.sh"

echo "dry-run: waiting for services to warm up"
sleep 2

client_url="http://${CLIENT_HOST}:${CLIENT_PORT}/"
card_url="http://${SERVER_HOST}:${SERVER_PORT}/agent/.well-known/agent-card.json"

echo "dry-run: checking client -> $client_url"
curl -fsS "$client_url" >/dev/null

echo "dry-run: checking server card -> $card_url"
card_json="$(curl -fsS "$card_url")"

agent_rpc_url="$(printf '%s' "$card_json" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("url",""))' 2>/dev/null || true)"
if [[ -z "$agent_rpc_url" ]]; then
  agent_rpc_url="$(printf '%s' "$card_json" | python -c 'import json,sys; print(json.load(sys.stdin).get("url",""))' 2>/dev/null || true)"
fi

if [[ -z "${agent_rpc_url:-}" ]]; then
  echo "dry-run: failed to parse Agent Card URL from $card_url"
  exit 1
fi

echo "dry-run: agent rpc url -> $agent_rpc_url"
if [[ "$agent_rpc_url" == *"/agent/agent"* ]]; then
  echo "dry-run: detected invalid Agent Card URL ($agent_rpc_url)"
  echo "dry-run: PUBLIC_BASE_URL likely includes '/agent' by mistake."
  echo "dry-run: set PUBLIC_BASE_URL to .../edge_agentapp/api (without /agent)"
  exit 1
fi

expected_public_base_url="${EXPECTED_PUBLIC_BASE_URL:-${PUBLIC_BASE_URL:-}}"
if [[ -n "${expected_public_base_url:-}" ]]; then
  expected_agent_rpc_url="${expected_public_base_url%/}/agent"
  if [[ "$agent_rpc_url" != "$expected_agent_rpc_url" ]]; then
    echo "dry-run: Agent Card URL mismatch."
    echo "dry-run: expected $expected_agent_rpc_url"
    echo "dry-run: got      $agent_rpc_url"
    exit 1
  fi
fi

echo "dry-run: checking JSON-RPC endpoint -> $agent_rpc_url"
rpc_status="$(curl -sS -o /dev/null -w '%{http_code}' \
  -H 'Content-Type: application/json' \
  --data '{"jsonrpc":"2.0","id":"dry-run","method":"tasks/get","params":{"id":"dry-run"}}' \
  "$agent_rpc_url" || true)"

if [[ "$rpc_status" == "404" || "$rpc_status" == "000" || -z "$rpc_status" ]]; then
  echo "dry-run: rpc endpoint check failed with HTTP $rpc_status"
  exit 1
fi

echo "dry-run: success"
