# VM Scripts

These scripts are the preferred Linux VM entrypoints for the backend team.
Run them from the `inno-fantasy` app root.

## First VM Check

```bash
bash scripts/preflight-backend.sh
```

This checks that `uv`, `.env`, backend imports, Codex CLI, API-Football key, and
OCI config values are present. It does not make live API calls.

## Start The Backend

```bash
bash scripts/start-backend.sh
```

Defaults:

- host: `127.0.0.1`
- port: `8000`
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
