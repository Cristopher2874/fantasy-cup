# Scripts Folder

This folder provides deployment-style process control without `systemctl`.

Defaults are aligned to your VM/Nginx mapping:

- Frontend static server: `127.0.0.1:6004`
- Backend API server: `127.0.0.1:10004`
- App prefix at reverse proxy: `/edge_agentapp/`

## Main Scripts

- `build_local_release.sh`
  - Run on your local machine (with npm available).
  - Builds renderer dependencies + production client bundle.
  - Produces `release/edge-agentapp-client-dist/` and `release/edge-agentapp-client-dist.tar.gz`.
- `start_server_bg.sh`
  - Starts backend with `nohup uv run __main__.py --host 127.0.0.1 --port 10004`.
- `start_client_bg.sh`
  - Starts static file server with `nohup python -m http.server 6004`.
  - Serves from `CLIENT_DIST_DIR` (auto-detect: `dist_web` first, else `app/client/shell/dist`).
- `start_all.sh`
  - Starts client + server in background.
- `stop_server.sh` / `stop_client.sh` / `stop_all.sh`
  - Stops services using PID files, with fallback process matching.
- `reset_all.sh`
  - Stop, clear stale PID files, then start both again.
- `dry_run.sh`
  - Starts both services and checks:
    - `http://127.0.0.1:6004/`
    - `http://127.0.0.1:10004/agent/.well-known/agent-card.json`

## Runtime Files

Generated on start:

- PID files: `run/`
- logs: `logs/`

## Common Commands

```bash
chmod +x scripts/*.sh

./scripts/build_local_release.sh
./scripts/start_all.sh
./scripts/dry_run.sh
./scripts/stop_all.sh
```

## VM Deploy Flow (No npm on VM)

1. Run `./scripts/build_local_release.sh` locally.
2. Copy `release/edge-agentapp-client-dist.tar.gz` to VM.
3. Extract on VM (example):
   - `mkdir -p /opt/edge-agentapp/dist`
   - `tar -xzf edge-agentapp-client-dist.tar.gz -C /opt/edge-agentapp/dist`
4. Start using extracted bundle:
   - `CLIENT_DIST_DIR=/opt/edge-agentapp/dist ./scripts/start_all.sh`

## Important Nginx + Agent Card Note

When running behind Nginx at `/edge_agentapp/api/`, set server env:

- `PUBLIC_BASE_URL=https://<your-host>/edge_agentapp/api`

Do not set `PUBLIC_BASE_URL` with `/agent` at the end.
The server appends `/agent` when publishing the Agent Card URL.

## Troubleshooting `message/stream` 404

If browser console shows:
- `HTTP error establishing stream for message/stream: 404`
- HTML 404 page in the response body

Check these quickly:

1. Agent Card URL:
   - `curl -fsS http://127.0.0.1:10004/agent/.well-known/agent-card.json`
   - Confirm `"url"` is `.../edge_agentapp/api/agent` (not `.../agent/agent`).
2. Nginx API route:
   - `location ^~ /edge_agentapp/api/ { proxy_pass http://127.0.0.1:10004/; }`
3. Frontend build variables used locally before packaging:
   - `VITE_PUBLIC_BASE_PATH=/edge_agentapp/`
   - `VITE_AGENT_SERVER_URL=/edge_agentapp/api/agent`
   - `VITE_AGENT_CONFIG_URL=/edge_agentapp/api/agent/config`

Use `./scripts/dry_run.sh` after start; it now validates Agent Card RPC URL shape and fails early on route mismatches.
For strict validation, run with:
- `EXPECTED_PUBLIC_BASE_URL=https://<your-host>/edge_agentapp/api ./scripts/dry_run.sh`

## Environment Overrides

You can override defaults per VM:

- `APP_NAME` (default `edge-agentapp`)
- `SERVER_HOST` / `SERVER_PORT` (default `127.0.0.1:10004`)
- `CLIENT_HOST` / `CLIENT_PORT` (default `127.0.0.1:6004`)
- `CLIENT_DIST_DIR` (default auto-detect: `dist_web` first, else `app/client/shell/dist`)
