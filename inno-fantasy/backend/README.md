# Inno Fantasy Backend

FastAPI service for the Fantasy Cup skill flow. The UI/auth team can treat this
backend as the game execution API: it accepts uploaded skill zips, validates
them, runs approved skills through Codex CLI, scores the generated claim against
the current source-of-truth file, and exposes progress plus score results.

## Run Locally

From this folder:

```powershell
uv run uvicorn main:app --host 127.0.0.1 --port 10006
```

On Linux VM deployments, prefer the app-level script from the `inno-fantasy`
root:

```bash
bash scripts/start-backend.sh
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

## Deployment Handoff Checklist

Before the UI team runs the backend on the VM:

1. Copy `.env.example` to `.env` in `inno-fantasy/backend`.
2. Fill only VM secrets and deployment credentials in `.env`:
   `APISPORTS_KEY` or `API_FOOTBALL_KEY`, OCI values, and
   `INNO_FANTASY_ADMIN_TOKEN`.
3. Review non-secret settings in `config/config.yaml`, especially
   `codex_runner.command`, `codex_runner.enable_search`, `server.*`, and
   `rate_limit.*`.
4. Install/verify Codex CLI on the VM.
5. Run `bash scripts/preflight-backend.sh`.
6. Generate public data before users upload skills.
7. Start the backend with `bash scripts/start-backend.sh`.
8. Point the UI at the proxied backend routes.

The UI team does not need `INNO_FANTASY_ADMIN_TOKEN` for the normal user flow.
They only need it if they are building or testing an admin-only manual rescore
tool that calls `POST /scores/{job_id}/score`.

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
| `admin_routes.score_write_requires_token` | Requires an admin token for manual rescoring | `true` |
| `admin_routes.score_write_header` | Header name used for manual rescoring token | `x-admin-token` |
| `server.root_path` | ASGI root path metadata for deployments mounted under a prefix | `""` |
| `server.cors_allowed_origins` | Exact UI origins allowed for cross-origin browser calls | `[]` |
| `server.cors_allow_credentials` | Whether CORS responses allow credentials/cookies | `false` |
| `server.trusted_hosts` | Allowed Host headers for Starlette trusted-host middleware | `["*"]` |
| `rate_limit.enabled` | Enables app-level in-memory request throttling | `true` |
| `rate_limit.trust_proxy_headers` | Uses `X-Forwarded-For` for client identity behind a proxy | `true` |
| `rate_limit.default` | Fallback request/window limit for routes without a custom rule | `120/min` |
| `rate_limit.rules` | Per-endpoint rate-limit buckets | See config |

Environment variables should be reserved for secrets or deployment-specific
credential paths:

- `APISPORTS_KEY` or `API_FOOTBALL_KEY`.
- OCI credential variables referenced by the existing `oci` config block.
- `INNO_FANTASY_ADMIN_TOKEN` for protected admin-only routes.

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

For the current full-app VM deployment that replaces `playtest_app`, prefer the
app-level web/proxy wrapper from `../scripts/start_bg.sh`. It keeps nginx pointed
at `127.0.0.1:6004` under `/edge_agentapp/`, serves the React build, and proxies
API routes to this backend on `127.0.0.1:10006`.

Recommended VM command behind a local reverse proxy:

```bash
cd /opt/fantasy-cup/inno-fantasy/backend
uv run uvicorn main:app --host 127.0.0.1 --port 10006 --proxy-headers --forwarded-allow-ips="127.0.0.1"
```

Preferred wrapper from the app root:

```bash
cd /opt/fantasy-cup/inno-fantasy
bash scripts/start-backend.sh
```

Use one uvicorn worker for the MVP. Pipeline progress is currently kept in
process memory while Codex runs in a FastAPI background task; multiple workers
can make `/progress/{job_id}` hit a different process than the upload.

If the proxy exposes the API under `/api`, prefer stripping that prefix before
forwarding to uvicorn. For example, with nginx:

```nginx
client_max_body_size 25m;

location /api/ {
    proxy_pass http://127.0.0.1:10006/;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Host $host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_buffering off;
    proxy_read_timeout 600s;
}
```

The trailing slash on `proxy_pass http://127.0.0.1:10006/;` is intentional: it
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

## Rate Limiting

The backend includes a small in-memory rate limiter in
`services/rate_limiter.py`. It is meant as a simple MVP safety rail and learning
implementation. Each client gets a separate counter per bucket, where a bucket
is a configured endpoint group such as `upload`, `progress`, or `score-read`.

Current defaults in `config/config.yaml`:

| Bucket | Match | Limit |
| --- | --- | --- |
| `upload` | `POST /upload` | 3 requests / 60 seconds |
| `progress` | `GET /progress...` | 120 requests / 60 seconds |
| `public-data` | `GET /public-data...` | 120 requests / 60 seconds |
| `score-read` | `GET /scores...` | 60 requests / 60 seconds |
| `score-write` | `POST /scores...` | 5 requests / 60 seconds |
| `default` | Any other route | 120 requests / 60 seconds |

When a client exceeds a bucket, the API returns `429` with:

```json
{
  "detail": "Rate limit exceeded. Try again later.",
  "rate_limit": {
    "bucket": "upload",
    "limit": 3,
    "retry_after_seconds": 42
  }
}
```

Responses also include `X-RateLimit-Bucket`, `X-RateLimit-Limit`,
`X-RateLimit-Remaining`, and when blocked, `Retry-After`.

Because this limiter is in memory, it protects the current single-worker VM
setup. If the app later runs multiple workers or multiple VMs, move rate limits
to the reverse proxy, Redis, or another shared store. Keep proxy-level rate
limits too; app-level rate limiting is a backup, not the only boundary.

Behind a reverse proxy, leave `rate_limit.trust_proxy_headers: true` only if the
backend is not directly reachable from the internet. If direct access is
possible, set it to `false` so users cannot spoof `X-Forwarded-For`.

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

`POST /scores/{job_id}/score` is an admin route. When
`admin_routes.score_write_requires_token` is `true`, call it with the configured
header:

```bash
curl -X POST \
  -H "x-admin-token: ${INNO_FANTASY_ADMIN_TOKEN}" \
  "http://127.0.0.1:10006/scores/<job_id>/score?force=true"
```

This protection does not affect automatic scoring inside the upload pipeline.

## Daily Data Schedule

The UI should assume data exists before uploads begin. On the VM, schedule the
scripts from the app root, `inno-fantasy`:

```bash
bash scripts/generate-game-data.sh public 2022-11-21
bash scripts/generate-game-data.sh truth 2022-11-21
```

Recommended production rhythm:

- Morning: generate public data for the upcoming matchday.
- Midday: users upload skills; Codex reads the generated public snapshot.
- Night: generate source of truth after matches finish; scoring uses that file.

Generated runtime data is written under `../data` and is ignored by Git. See
`../data/README.md` for the data contract and sample file shapes.
