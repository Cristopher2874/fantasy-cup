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
  or configured with `FANTASY_CUP_CODEX_COMMAND`.
- API-Football credentials are required for scheduled data generation:
  `APISPORTS_KEY` or `API_FOOTBALL_KEY`.
- OCI guardrail credentials are expected to be configured in the deployment
  environment for validation.
- Auth is intentionally left to the consuming platform or gateway.

Useful environment variables:

| Variable | Purpose | Default |
| --- | --- | --- |
| `FANTASY_CUP_CODEX_COMMAND` | Codex CLI command/path | `codex` |
| `FANTASY_CUP_CODEX_SANDBOX` | Codex sandbox mode | `read-only` |
| `FANTASY_CUP_CODEX_TIMEOUT_SECONDS` | Per-skill Codex timeout | `300` |
| `FANTASY_CUP_CODEX_ENABLE_SEARCH` | Enables Codex web search for special tests | `false` |
| `FANTASY_CUP_INITIAL_TEAM_POINTS` | Starting bankroll used by risk scoring | `0` |
| `API_FOOTBALL_MIN_INTERVAL_SECONDS` | Delay between API-Football calls | `7.0` |
| `API_FOOTBALL_RATE_LIMIT_RETRIES` | API-Football retry attempts | `5` |
| `API_FOOTBALL_RATE_LIMIT_SLEEP_SECONDS` | Sleep after rate-limit responses | `20.0` |

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
