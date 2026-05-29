# Simple Codex Skill Runner

This folder is a minimal local test harness for running one submitted skill through Codex CLI and saving the generated Fantasy Cup submission locally.

The default runner is intentionally clean:

- Python loads the selected skill file.
- Python passes stable folder paths and the shared JSON contract.
- Codex reads the local public files itself.
- Codex returns one JSON object.
- Python saves it as `submission.json` and performs a basic shape check.

The runner does not embed `players.json`, `risk_claims.json`, schema contents, or other public data into the prompt.

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

Codex web search is enabled as a general capability. The shared runner prompt does not decide whether to use it; the selected skill does.

## Runner Constants

Useful constants in `ingestion/run_pick.py`:

```python
CODEX_COMMAND = "codex"
CODEX_SANDBOX_MODE = "read-only"
ENABLE_CODEX_SEARCH_CAPABILITY = True
ENABLE_WINDOWS_CODEX_WORKAROUNDS = True
```

## Windows Workarounds

Windows Codex CLI may fail before PowerShell starts with:

```text
windows sandbox: spawn setup refresh
```

Those workarounds are isolated in:

```text
ingestion/windows_codex_workarounds.py
```

They are enabled in this test file with:

```python
ENABLE_WINDOWS_CODEX_WORKAROUNDS = True
```

Linux/macOS users can set it to `False`.

That optional module:

- Prefers the standalone Codex binary under `%USERPROFILE%\.codex\packages\standalone\releases\...\bin\codex.exe`.
- Forces `...\codex-resources` and `...\bin` to the front of the Codex subprocess `PATH`.
- Adds Windows-specific prompt guidance for simple PowerShell reads.

It still does not inject public-data file contents into the prompt.
