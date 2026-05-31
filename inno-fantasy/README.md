# Inno Fantasy

Inno Fantasy is the final standalone app for the fantasy World Cup pipeline.
The production flow lives in the backend. The included frontend can be built
and served by the VM wrapper for the current full-app deployment, while auth
can still be owned by the gateway or a team-owned platform layer.

## App Modules

| Path | Purpose |
| --- | --- |
| `backend/` | FastAPI app, upload routes, validation, Codex execution, public data access, progress, scoring, config, and deployment settings. |
| `backend/routes/` | HTTP endpoints consumed by the UI: uploads, progress, public data, and scores. |
| `backend/services/validator/` | Validates uploaded skill ZIPs before execution. |
| `backend/services/pipeline.py` | Connects validation, Codex execution, and scoring for the MVP end-to-end flow. |
| `backend/services/codex_runner/` | Runs the validated skill through Codex CLI and stores generated claims. |
| `backend/services/data_generator/` | Generates public data and source-of-truth JSON from API-Football. |
| `backend/services/score_engine.py` | Compares Codex claims against source-of-truth data and writes score results. |
| `backend/config/` | Non-secret runtime configuration loaded from `config.yaml`. |
| `data/` | Generated JSON files and small samples that show expected public-data, source-of-truth, run, claim, and score shapes. |
| `scripts/` | Preferred Linux VM entrypoints for final app startup, backend startup, and daily data generation. |
| `skills/` | Example app skill content. |
| `frontend/` | React UI for the final VM-facing app build. Auth is still expected to live at the gateway or consuming platform layer. |

## Runtime Flow

1. Morning data job generates public JSON for the match day.
2. Users upload ZIP skills through the backend upload endpoint.
3. The validator checks the ZIP structure and rejects unsafe or invalid files.
4. Valid skills enter the pipeline and are executed by Codex CLI.
5. Codex writes the claim JSON into the run folder.
6. After matches are complete, the source-of-truth job generates real results.
7. The scoring service compares claims against the source of truth and exposes
   final results to the UI.

For the current MVP, automatic scoring can run immediately after Codex finishes
when the source-of-truth file already exists. In a real match-day cycle, claims
would be stored first and scored after the post-match source-of-truth job runs.

## Preferred VM Commands

Run these from the `inno-fantasy` app root on the Linux VM.

First setup check:

```bash
bash scripts/preflight-backend.sh
```

Generate public data before users upload skills:

```bash
bash scripts/generate-game-data.sh public 2022-11-21
```

Start the final app on the existing `/edge_agentapp/` nginx route:

```bash
bash scripts/start_bg.sh
```

Inspect or stop the deployed app:

```bash
bash scripts/status.sh
bash scripts/stop.sh
```

Start the backend only:

```bash
bash scripts/start-backend.sh
```

Generate source of truth after matches finish:

```bash
bash scripts/generate-game-data.sh truth 2022-11-21
```

For local historical testing where public data and truth are both generated for
the same date:

```bash
bash scripts/generate-game-data.sh all 2022-11-21
```

## How Scripts Map To Backend Code

| Script | Calls | Use |
| --- | --- | --- |
| `scripts/preflight-backend.sh` | Imports `backend/main.py` and checks config/Codex/API credentials | VM readiness check before sharing with the UI team. |
| `scripts/start_bg.sh` | Starts `backend/main.py` on `127.0.0.1:10006` and `server.py` on `127.0.0.1:6004` | Runs the full VM app behind the existing `/edge_agentapp/` nginx route. |
| `scripts/run_fg.sh` | Same app stack as `start_bg.sh`, with the web/proxy server in the foreground | Foreground smoke test or manual VM run. |
| `scripts/start-backend.sh` | `uv run uvicorn main:app` from `backend/` | Starts only the FastAPI backend. |
| `scripts/generate-game-data.sh public` | `scripts/generate-public-data.sh` -> `python -m services.daily_source_gen` | Creates public data consumed by uploaded skills. |
| `scripts/generate-game-data.sh truth` | `scripts/generate-source-truth.sh` -> `python -m services.daily_truth_gen` | Creates source-of-truth data consumed by scoring. |

## Backend Integration Notes

- Run backend commands from `backend/` or use the root scripts above.
- Keep secrets in `backend/.env`; keep non-secret config in
  `backend/config/config.yaml`.
- The normal UI upload/progress/score-read flow does not need the admin scoring
  token.
- `POST /scores/{job_id}/score` is an admin/manual rescore endpoint and may
  require `INNO_FANTASY_ADMIN_TOKEN`.
- Keep `BACKEND_WORKERS=1` for the MVP because progress state is in-process.
  Use a shared queue/store before running multiple backend workers.

More detailed docs:

- `backend/README.md`
- `data/README.md`
- `scripts/README.md`
