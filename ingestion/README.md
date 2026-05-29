# Simple Codex Skill Runner

This folder is a minimal local test harness for running one submitted skill through Codex CLI and saving the generated Fantasy Cup submission locally.

The runner is intentionally generic:

- Python loads the selected skill file.
- Python injects the same shared public data and JSON contract every time.
- Codex returns one JSON object.
- Python saves it as `submission.json` and performs a basic validity check.

The skill controls the strategy. A skill may be conservative, use risk claims, request web research, or define team-specific behavior.

## Run

From the project root:

```powershell
uv run python ingestion/run_pick.py
```

The runner creates:

```text
ingestion/outputs/<timestamp>/
  prompt.md
  codex.stdout.log
  codex.stderr.log
  codex.final-message.txt
  submission.json
```

## Switch Skills

Edit only this constant near the top of `ingestion/run_pick.py`:

```python
ACTIVE_SKILL_PATH = SKILL_VALID_PICK
# ACTIVE_SKILL_PATH = SKILL_WEB_RESEARCH_RISK_PICK
```

Then run:

```powershell
uv run python ingestion/run_pick.py
```

## Included Test Skills

- `skills/generate_valid_pick.md` - creates a valid local-data submission.
- `skills/web_research_risk_pick.md` - asks Codex to use web research to choose a risk play.

Codex web search is enabled for the run as a general capability. The shared runner prompt does not decide whether to use it; the selected skill does.

## Runner Constants

Useful constants in `ingestion/run_pick.py`:

```python
CODEX_COMMAND = "codex"
CODEX_PATH_FIX = "auto"
ENABLE_CODEX_SEARCH_CAPABILITY = True
DRY_RUN = False
```

On Windows, `CODEX_PATH_FIX = "auto"` prepares the Codex subprocess path so the Windows sandbox helper can be discovered when needed.
