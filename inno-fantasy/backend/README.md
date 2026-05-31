# Inno Fantasy Backend

FastAPI service for the Fantasy Cup skill flow. The UI/auth team can treat this
backend as the game execution API: it accepts uploaded skill zips, validates
them, runs approved skills through Codex CLI, scores the generated claim against
the current source-of-truth file, and exposes progress plus score results.

## Run Locally

From this folder:

```powershell
uv run uvicorn main:app --host 127.0.0.1 --port 8000
```

Health check:

```http
GET /health
```

The backend uses local imports, so run commands from `inno-fantasy/backend`.

## Required Runtime Services

- `codex` CLI must be installed on the deployment host and available on `PATH`,
  or configured with `codex_runner.command` in `config/config.yaml`.
- API-Football credentials are required for scheduled data generation:
  `APISPORTS_KEY` or `API_FOOTBALL_KEY`.
- OCI guardrail credentials are expected to be configured in the deployment
  environment for validation.
- Auth is intentionally left to the consuming platform or gateway.

## Configuration

Non-secret operational settings live in `config/config.yaml`:

| YAML key | Purpose | Default |
| --- | --- | --- |
| `game.default_league_id` | API-Football league id for scheduled jobs | `"1"` |
| `game.default_season` | API-Football season for scheduled jobs | `"2022"` |
| `codex_runner.command` | Codex CLI command/path | `codex` |
| `codex_runner.sandbox` | Codex sandbox mode | `read-only` |
| `codex_runner.timeout_seconds` | Per-skill Codex timeout | `300` |
| `codex_runner.enable_search` | Enables Codex web search for special tests | `false` |
| `codex_runner.log_output_chars` | Max stdout/stderr characters echoed to uvicorn logs on failure | `4000` |
| `api_football.min_interval_seconds` | Delay between API-Football calls | `7.0` |
| `api_football.rate_limit_retries` | API-Football retry attempts | `5` |
| `api_football.rate_limit_sleep_seconds` | Sleep after rate-limit responses | `20.0` |
| `scoring.initial_team_points` | Starting bankroll used by risk scoring | `0` |
| `server.root_path` | ASGI root path metadata for deployments mounted under a prefix | `""` |
| `server.cors_allowed_origins` | Exact UI origins allowed for cross-origin browser calls | `[]` |
| `server.cors_allow_credentials` | Whether CORS responses allow credentials/cookies | `false` |
| `server.trusted_hosts` | Allowed Host headers for Starlette trusted-host middleware | `["*"]` |

Environment variables should be reserved for secrets or deployment-specific
credential paths:

- `APISPORTS_KEY` or `API_FOOTBALL_KEY`.
- OCI credential variables referenced by the existing `oci` config block.

## Codex CLI Deployment Notes

The upload pipeline calls Codex through
`services/codex_runner/skill_runner.py`. Local Windows development uses helper
logic in `services/codex_runner/windows_helpers.py`, but that helper detects the
host OS. On Linux it falls back to normal command resolution with `PATH` and
does not inject Windows-specific prompt guidance.

For a Linux VM, install Codex CLI and either keep it on `PATH` or set the full
binary path:

```yaml
codex_runner:
  command: /usr/local/bin/codex
  sandbox: read-only
```

Before running uploads on a new deployment, verify the CLI contract expected by
the runner:

```bash
which codex
codex --version
printf 'Return exactly {"ok": true} and no markdown.' | codex --sandbox read-only exec --output-last-message /tmp/codex-test.txt -
cat /tmp/codex-test.txt
```

If the deployed Codex CLI uses a different syntax than
`codex --sandbox read-only exec --output-last-message <file> -`, update
`skill_runner.py` or the `codex_runner.command` config before enabling the
upload flow. When Codex fails, uvicorn logs include the run directory plus
stdout/stderr tails, and the full artifacts are written under `../data/runs/`.

## Reverse Proxy Deployment Notes

The backend routes are relative and do not hardcode a public host. A reverse
proxy can safely expose them as long as it forwards to the same route paths the
FastAPI app defines.

Recommended VM command behind a local reverse proxy:

```bash
cd /opt/fantasy-cup/inno-fantasy/backend
uv run uvicorn main:app --host 127.0.0.1 --port 8000 --proxy-headers --forwarded-allow-ips="127.0.0.1"
```

Use one uvicorn worker for the MVP. Pipeline progress is currently kept in
process memory while Codex runs in a FastAPI background task; multiple workers
can make `/progress/{job_id}` hit a different process than the upload.

If the proxy exposes the API under `/api`, prefer stripping that prefix before
forwarding to uvicorn. For example, with nginx:

```nginx
client_max_body_size 25m;

location /api/ {
    proxy_pass http://127.0.0.1:8000/;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Host $host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_buffering off;
    proxy_read_timeout 600s;
}
```

The trailing slash on `proxy_pass http://127.0.0.1:8000/;` is intentional: it
forwards `/api/upload` to backend route `/upload`. If the proxy does not strip
the prefix, the backend routes will not match `/api/...` without additional
routing changes.

For same-origin deployments through the reverse proxy, leave
`server.cors_allowed_origins` empty. If the UI calls the backend from another
origin during integration, add exact origins in `config/config.yaml`:

```yaml
server:
  cors_allowed_origins:
    - https://ui.example.com
  cors_allow_credentials: true
```

If the backend is mounted under a prefix and the proxy already strips that
prefix, `server.root_path` can be set for OpenAPI/docs metadata:

```yaml
server:
  root_path: /api
```

## UI Integration Endpoints

### Upload and validation

```http
POST /upload
Content-Type: multipart/form-data
```

Form fields:

- `file`: one zip upload, repeatable.
- `files`: alternate repeatable zip field.
- `team_id`: optional team/user identifier from the UI platform.

Valid skill zips are queued automatically for Codex execution. The response
contains validation results plus `execution_job_id` for each accepted upload.

### Pipeline progress

```http
GET /progress
GET /progress/{job_id}
GET /progress/{job_id}/stream
```

The stream endpoint is server-sent events and emits the job object whenever the
stage changes. Important stages are `queued`, `snapshot`, `codex`, `scoring`,
`scored`, and failure stages such as `scoring_failed`.

### Public data

```http
GET /public-data
GET /public-data/files/{file_name}
GET /public-data/matchdays/{YYYY-MM-DD}
GET /public-data/matchdays/{YYYY-MM-DD}/files/{file_name}
```

These are read-only files generated before users upload skills. Typical files
are `manifest.json`, `matchday.json`, `matches.json`, `players.json`, and
`risk_claims.json`.

### Scores

```http
GET /scores
GET /scores/{job_id}
POST /scores/{job_id}/score?force=false
```

The pipeline scores automatically after Codex succeeds. The manual score route
is mainly for local repair/replay after a source-of-truth file is generated.
Use `force=true` only when intentionally replacing a previous score for the
same job.

## Daily Data Schedule

The UI should assume data exists before uploads begin. On the VM, schedule the
scripts from the app root, `inno-fantasy`:

```bash
./scripts/generate-public-data.sh 2022-11-21
./scripts/generate-source-truth.sh 2022-11-21
```

Recommended production rhythm:

- Morning: generate public data for the upcoming matchday.
- Midday: users upload skills; Codex reads the generated public snapshot.
- Night: generate source of truth after matches finish; scoring uses that file.

Generated runtime data is written under `../data` and is ignored by Git. See
`../data/README.md` for the data contract and sample file shapes.
