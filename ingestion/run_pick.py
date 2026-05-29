from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    from codex_environment import prepare_codex_environment
except ModuleNotFoundError:
    from ingestion.codex_environment import prepare_codex_environment


PROJECT_ROOT = Path(__file__).resolve().parent.parent
INGESTION_ROOT = PROJECT_ROOT / "ingestion"
PUBLIC_DATA_DIR = PROJECT_ROOT / "team_submission" / "public_data"
SCHEMA_PATH = PROJECT_ROOT / "team_submission" / "schemas" / "team_submission.schema.json"
OUTPUT_ROOT = INGESTION_ROOT / "outputs"

SKILL_VALID_PICK = INGESTION_ROOT / "skills" / "generate_valid_pick.md"
SKILL_WEB_RESEARCH_RISK_PICK = INGESTION_ROOT / "skills" / "web_research_risk_pick.md"

# Switch only this constant to test a different submitted skill.
# ACTIVE_SKILL_PATH = SKILL_VALID_PICK
ACTIVE_SKILL_PATH = SKILL_WEB_RESEARCH_RISK_PICK

CODEX_COMMAND = "codex"
CODEX_PATH_FIX = "auto"  # "auto", "always", or "off"
ENABLE_CODEX_SEARCH_CAPABILITY = True
DRY_RUN = False

PUBLIC_DATA_FILES = [
    "manifest.json",
    "matchday.json",
    "matches.json",
    "teams.json",
    "players.json",
    "risk_claims.json",
    "answer_template.json",
]


def timestamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S-%f")


def read_text(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f"Missing required file: {path}")
    return path.read_text(encoding="utf-8")


def build_prompt(skill_text: str) -> str:
    public_data_blocks = []
    for file_name in PUBLIC_DATA_FILES:
        path = PUBLIC_DATA_DIR / file_name
        public_data_blocks.append(
            f"--- {file_name} ---\n{read_text(path)}\n--- end {file_name} ---"
        )

    return f"""You are Codex CLI running a Fantasy Cup skill execution.

Execute the submitted skill using the local public data provided below. The skill
is the source of strategy and decision-making. Return only the final team
submission JSON object; do not wrap it in markdown fences.

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

JSON schema:
{read_text(SCHEMA_PATH)}

Local public data:
{chr(10).join(public_data_blocks)}
"""


def extract_json_object(text: str) -> dict[str, Any]:
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


def validate_submission(path: Path) -> tuple[bool, list[str]]:
    errors: list[str] = []
    if not path.exists():
        return False, [f"Missing expected file: {path}"]

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        return False, [f"submission.json is not valid JSON: {error}"]

    for key in ("team_id", "team_name", "matchday_id", "answers"):
        if key not in payload:
            errors.append(f"Missing top-level key: {key}")

    answers = payload.get("answers")
    if not isinstance(answers, dict):
        errors.append("answers must be an object")
        return False, errors

    valid_record_ids = {
        item.get("record_id")
        for item in json.loads((PUBLIC_DATA_DIR / "players.json").read_text(encoding="utf-8"))
        if isinstance(item, dict)
    }

    fantasy_xi = answers.get("fantasy_xi")
    if not isinstance(fantasy_xi, list) or len(fantasy_xi) != 11:
        errors.append("answers.fantasy_xi must contain exactly 11 entries")
    else:
        for index, item in enumerate(fantasy_xi, start=1):
            record_id = item.get("record_id") if isinstance(item, dict) else None
            if not isinstance(record_id, str) or ":" not in record_id:
                errors.append(f"fantasy_xi entry {index} must be an object with record_id like match_id:player_id")
            elif record_id not in valid_record_ids:
                errors.append(f"fantasy_xi entry {index} record_id is not in players.json: {record_id}")

    if "risk_play" not in answers:
        errors.append("answers.risk_play is required; use null if no risk play is selected")
    elif answers["risk_play"] is not None:
        risk_play = answers["risk_play"]
        if not isinstance(risk_play, dict):
            errors.append("answers.risk_play must be null or an object")
        else:
            claims_payload = json.loads((PUBLIC_DATA_DIR / "risk_claims.json").read_text(encoding="utf-8"))
            available_claims = claims_payload.get("available_claims", [])
            matching_claim = next(
                (
                    claim
                    for claim in available_claims
                    if claim.get("claim_id") == risk_play.get("claim_id")
                    and str(claim.get("match_id")) == str(risk_play.get("match_id"))
                ),
                None,
            )
            if not matching_claim:
                errors.append("answers.risk_play must use a claim_id and match_id pair from risk_claims.json")
            else:
                for required_field in matching_claim.get("required_fields", []):
                    if required_field not in risk_play:
                        errors.append(f"answers.risk_play is missing required field: {required_field}")

    strategy_summary = answers.get("strategy_summary")
    if not isinstance(strategy_summary, str) or not strategy_summary.strip():
        errors.append("answers.strategy_summary must be a non-empty string")

    return not errors, errors


def write_submission(output_dir: Path, response_text: str) -> tuple[bool, list[str]]:
    try:
        payload = extract_json_object(response_text)
    except ValueError as error:
        return False, [str(error)]

    submission_path = output_dir / "submission.json"
    submission_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return validate_submission(submission_path)


def main() -> int:
    output_dir = (OUTPUT_ROOT / timestamp()).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        skill_text = read_text(ACTIVE_SKILL_PATH.resolve())
        prompt_text = build_prompt(skill_text)
    except FileNotFoundError as error:
        print(error, file=sys.stderr)
        return 2

    prompt_path = output_dir / "prompt.md"
    stdout_path = output_dir / "codex.stdout.log"
    stderr_path = output_dir / "codex.stderr.log"
    final_message_path = output_dir / "codex.final-message.txt"
    prompt_path.write_text(prompt_text, encoding="utf-8")

    print(f"Output folder: {output_dir}")
    print(f"Prompt file: {prompt_path}")
    print(f"Skill file: {ACTIVE_SKILL_PATH.resolve()}")

    if DRY_RUN:
        print("Dry run complete. Codex CLI was not called.")
        return 0

    codex_env = prepare_codex_environment(CODEX_COMMAND, path_fix=CODEX_PATH_FIX)
    command = [codex_env.command]
    if ENABLE_CODEX_SEARCH_CAPABILITY:
        command.append("--search")
    command.extend(["exec", "--output-last-message", str(final_message_path), "-"])

    try:
        result = subprocess.run(
            command,
            cwd=PROJECT_ROOT,
            env=codex_env.env,
            input=prompt_text,
            text=True,
            capture_output=True,
            check=False,
        )
    except FileNotFoundError:
        print(f"Codex CLI was not found: {CODEX_COMMAND}", file=sys.stderr)
        print("Install Codex CLI or set CODEX_COMMAND with the full executable path.", file=sys.stderr)
        return 2
    except PermissionError as error:
        print(f"Codex CLI could not be executed: {error}", file=sys.stderr)
        return 2

    stdout_path.write_text(result.stdout, encoding="utf-8")
    stderr_path.write_text(result.stderr, encoding="utf-8")

    if result.returncode != 0:
        print(f"Codex CLI exited with code {result.returncode}. See {stderr_path}", file=sys.stderr)
        return result.returncode

    response_text = final_message_path.read_text(encoding="utf-8") if final_message_path.exists() else result.stdout
    is_valid, errors = write_submission(output_dir, response_text)
    if not is_valid:
        print("Codex finished, but its final response could not be saved as a valid submission:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print(f"Generated valid-looking submission: {output_dir / 'submission.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
