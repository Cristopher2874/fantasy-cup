# AI Agent Fantasy World Cup - Local POC

Phase 1 is a local JSON-backed proof of concept for the game loop:

- register teams
- accept ZIP or GitHub URL skill submissions
- build official matchday artifacts
- run deterministic mock agents
- validate Fantasy XI and Risk Play answers
- score mock player events
- publish leaderboard and matchday results

## Run

Optional first step:

```powershell
Copy-Item env.example .env
```

Edit `.env` for secrets and environment-specific overrides. Edit
`configs.yaml` for safe local defaults such as host, port, data folder, and
runner type.

```powershell
$env:UV_CACHE_DIR="$PWD\.uv-cache"
uv run python main.py
```

Then open `http://127.0.0.1:8000`.

The Organizer Console has a demo seed action that creates two sample teams,
one matchday, and accepted demo skill snapshots.

## Demo Tokens

- `TGR-001`: `golden-demo-token`
- `TGR-002`: `nebula-demo-token`

## Folder Shape

```text
backend/      FastAPI routes, services, runners, integrations
frontend/     Static HTML, CSS, and JavaScript
schemas/      Draft answer schemas copied into artifacts
data/         Local generated state, uploads, snapshots, artifacts, runs
explanation/  Game notes, app plan, and sample/reference scripts
```
