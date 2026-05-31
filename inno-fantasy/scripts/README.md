# VM Scripts

These scripts are the preferred Linux VM entrypoints for the backend team.
Run them from the `inno-fantasy` app root.

## Full App On The Existing Nginx Route

Use this when replacing the old `playtest_app` route with the final app. The
public web/proxy process binds to the same default port as the playtest app:
`127.0.0.1:6004`. It serves `frontend/inno-fantasy/build` with Python and
proxies API requests to the FastAPI backend on `127.0.0.1:10006`.

Because the VM does not need npm, build the frontend before copying or syncing
the app to the VM:

```bash
cd frontend/inno-fantasy
npm run build
```

Then on the VM, from the `inno-fantasy` app root:

```bash
bash scripts/preflight-backend.sh
bash scripts/run_fg.sh
```

Or start it in the background:

```bash
bash scripts/start_bg.sh
bash scripts/status.sh
bash scripts/stop.sh
```

Defaults:

- public web/proxy host: `127.0.0.1`
- public web/proxy port: `6004`
- backend host: `127.0.0.1`
- backend port: `10006`
- frontend build: `frontend/inno-fantasy/build`

Optional overrides:

```bash
INNO_FANTASY_PORT=6004 BACKEND_PORT=10006 LOG_LEVEL=debug bash scripts/start_bg.sh
```

The matching nginx location is in `scripts/nginx_inno_fantasy.conf.example`:

```nginx
location ^~ /edge_agentapp/ {
    proxy_pass http://127.0.0.1:6004/;
}
```

Open the public app with the trailing slash: `/edge_agentapp/`.

## First VM Check

```bash
bash scripts/preflight-backend.sh
```

This checks that `uv`, `.env`, backend imports, Codex CLI, API-Football key, and
OCI config values are present. It does not make live API calls.

## Start The Backend Only

```bash
bash scripts/start-backend.sh
```

Defaults:

- host: `127.0.0.1`
- port: `10006`
- proxy headers: enabled
- workers: `1`

Optional overrides:

```bash
BACKEND_PORT=8080 LOG_LEVEL=debug bash scripts/start-backend.sh
```

Keep `BACKEND_WORKERS=1` for the current MVP because progress state is stored in
the running backend process.

## Generate Game Data

Morning public data:

```bash
bash scripts/generate-game-data.sh public 2022-11-21
```

Night source of truth:

```bash
bash scripts/generate-game-data.sh truth 2022-11-21
```

Local historical simulation:

```bash
bash scripts/generate-game-data.sh all 2022-11-21
```

The wrapper calls the lower-level scripts:

- `generate-public-data.sh`
- `generate-source-truth.sh`

Use those directly only when you need advanced flags such as `REFRESH=1`,
`ALLOW_INCOMPLETE=1`, or explicit `FIXTURE_IDS`.
