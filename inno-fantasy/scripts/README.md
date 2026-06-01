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

## Codex CLI Setup

The upload pipeline needs Codex CLI on the VM user that runs the backend. The
backend reads `codex_runner.command` from `backend/config/config.yaml`; the
default is `codex` on `PATH`.

Install Codex CLI on Linux:

```bash
curl -fsSL https://chatgpt.com/codex/install.sh | sh
```

For a non-interactive install:

```bash
curl -fsSL https://chatgpt.com/codex/install.sh | CODEX_NON_INTERACTIVE=1 sh
```

Then open a new shell or source the shell profile updated by the installer, and
verify:

```bash
command -v codex
codex --version
```

Install `bubblewrap` so Codex can use the Linux sandbox package from the OS
instead of its bundled fallback:

```bash
# Ubuntu/Debian
sudo apt install bubblewrap

# Fedora/RHEL/Oracle Linux
sudo dnf install bubblewrap
```

Authenticate as the same Linux user that runs `scripts/start_bg.sh`:

```bash
codex
```

For SSH-only servers, copy the URL printed by Codex into your local browser and
complete login there. After login, test the exact non-interactive shape used by
the backend:

```bash
bash scripts/codex-smoke-test.sh
```

The smoke test mirrors the runner shape: `codex --sandbox read-only --search
exec --skip-git-repo-check ...`. To disable the search flag for diagnosis:

```bash
CODEX_ENABLE_SEARCH=0 bash scripts/codex-smoke-test.sh
```

If the CLI still prints `Not inside a trusted directory`, verify
`codex_runner.skip_git_repo_check: true` in `backend/config/config.yaml` and
rerun the smoke test from `inno-fantasy/`.

Prefer saved CLI auth for this app. Avoid exporting `CODEX_API_KEY` into the
long-running backend environment because uploaded skill text is untrusted and
the Codex subprocess inherits the backend environment.

If `codex` is installed outside `PATH`, set the full executable path in
`backend/config/config.yaml`:

```yaml
codex_runner:
  command: /home/cris/.local/bin/codex
  enable_search: true
  skip_git_repo_check: true
```

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
