from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
INGESTION_ROOT = PROJECT_ROOT / "ingestion"
PUBLIC_DATA_DIR = PROJECT_ROOT / "team_submission" / "public_data"
SCHEMA_PATH = PROJECT_ROOT / "team_submission" / "schemas" / "team_submission.schema.json"
OUTPUT_ROOT = INGESTION_ROOT / "outputs"

SKILL_VALID_PICK = INGESTION_ROOT / "skills" / "generate_valid_pick.md"
SKILL_WEB_RESEARCH_RISK_PICK = INGESTION_ROOT / "skills" / "web_research_risk_pick.md"

# Switch this constant to test a different submitted skill.
# ACTIVE_SKILL_PATH = SKILL_VALID_PICK
ACTIVE_SKILL_PATH = SKILL_WEB_RESEARCH_RISK_PICK

CODEX_COMMAND = "codex"
CODEX_SANDBOX_MODE = "read-only"
ENABLE_CODEX_SEARCH_CAPABILITY = True
ENABLE_WINDOWS_CODEX_WORKAROUNDS = True


def timestamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S-%f")


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def resolve_codex_launch() -> tuple[str, dict[str, str], str, list[str]]:
    if not ENABLE_WINDOWS_CODEX_WORKAROUNDS:
        return shutil.which(CODEX_COMMAND) or CODEX_COMMAND, dict(os.environ), "", []

    try:
        from windows_codex_workarounds import prepare_windows_codex_launch
    except ModuleNotFoundError:
        from ingestion.windows_codex_workarounds import prepare_windows_codex_launch

    launch = prepare_windows_codex_launch(CODEX_COMMAND)
    return launch.command, launch.env, launch.prompt_guidance, launch.notes


def build_prompt(skill_text: str, platform_guidance: str) -> str:
    platform_section = f"\nPlatform-specific guidance:\n{platform_guidance}\n" if platform_guidance else ""
    return f"""You are Codex CLI running a Fantasy Cup skill execution.

Execute the submitted skill using the local files available in this workspace.
The skill is the source of strategy and decision-making. Return only the final
team submission JSON object; do not wrap it in markdown fences.

Shared local context:
- Project root: {PROJECT_ROOT}
- Public data folder: {PUBLIC_DATA_DIR}
- Submission schema: {SCHEMA_PATH}
- Expected public files: manifest.json, matchday.json, matches.json, teams.json, players.json, risk_claims.json, answer_template.json

Use the selected skill to decide which files to inspect and whether to use web
research. Do not assume the public data contents are already present in this
prompt.
{platform_section}
Shared output contract:
- Return exactly one JSON object.
- The object must have `team_id`, `team_name`, `matchday_id`, and `answers`.
- `answers.fantasy_xi` must contain exactly 11 entries.
- Every Fantasy XI entry must use this shape: {{ "record_id": "match_id:player_id" }}.
- Every `record_id` must be present in `players.json`.
- `answers.risk_play` must be `null` or a valid risk claim object from `risk_claims.json`.
- `answers.strategy_summary` must be a non-empty string.

Submitted skill:
{skill_text}
"""


def extract_json_object(text: str) -> dict:
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        stripped = "\n".join(lines).strip()

    decoder = json.JSONDecoder()
    for index, char in enumerate(stripped):
        if char != "{":
            continue
        try:
            payload, _ = decoder.raw_decode(stripped[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload
    raise ValueError("Could not find a JSON object in Codex's final response.")


def main() -> int:
    output_dir = OUTPUT_ROOT / timestamp()
    output_dir.mkdir(parents=True, exist_ok=True)

    codex_command, codex_env, platform_guidance, notes = resolve_codex_launch()
    prompt_text = build_prompt(read_text(ACTIVE_SKILL_PATH), platform_guidance)

    prompt_path = output_dir / "prompt.md"
    final_message_path = output_dir / "codex.final-message.txt"
    stdout_path = output_dir / "codex.stdout.log"
    stderr_path = output_dir / "codex.stderr.log"
    submission_path = output_dir / "submission.json"
    prompt_path.write_text(prompt_text, encoding="utf-8")

    print(f"Output folder: {output_dir.resolve()}")
    print(f"Skill file: {ACTIVE_SKILL_PATH.resolve()}")
    print(f"Codex command: {codex_command}")
    print(f"Windows workarounds enabled: {ENABLE_WINDOWS_CODEX_WORKAROUNDS}")
    for note in notes:
        print(f"Note: {note}")

    command = [codex_command, "--sandbox", CODEX_SANDBOX_MODE]
    if ENABLE_CODEX_SEARCH_CAPABILITY:
        command.append("--search")
    command.extend(["exec", "--output-last-message", str(final_message_path), "-"])

    result = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        env=codex_env,
        input=prompt_text,
        text=True,
        capture_output=True,
        check=False,
    )

    stdout_path.write_text(result.stdout, encoding="utf-8")
    stderr_path.write_text(result.stderr, encoding="utf-8")

    if result.returncode != 0:
        print(f"Codex CLI exited with code {result.returncode}. See {stderr_path}", file=sys.stderr)
        return result.returncode

    response_text = final_message_path.read_text(encoding="utf-8") if final_message_path.exists() else result.stdout
    submission = extract_json_object(response_text)
    submission_path.write_text(json.dumps(submission, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Submission written: {submission_path.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
