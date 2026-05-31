"""Codex CLI execution for validated Fantasy Cup skills."""
from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from backend.services.codex_runner.windows_helpers import prepare_windows_codex_launch


CODEX_COMMAND = os.getenv("FANTASY_CUP_CODEX_COMMAND", "codex")
CODEX_SANDBOX_MODE = os.getenv("FANTASY_CUP_CODEX_SANDBOX", "read-only")
CODEX_TIMEOUT_SECONDS = int(os.getenv("FANTASY_CUP_CODEX_TIMEOUT_SECONDS", "300"))
ENABLE_CODEX_SEARCH = os.getenv("FANTASY_CUP_CODEX_ENABLE_SEARCH", "false").casefold() in {"1", "true", "yes"}

BACKEND_ROOT = Path(__file__).resolve().parents[2]
INNO_ROOT = BACKEND_ROOT.parent


@dataclass(frozen=True)
class CodexRunRequest:
    job_id: str
    team_id: str | None
    skill_name: str | None
    skill_dir: Path
    public_data_dir: Path
    schema_path: Path
    run_dir: Path


@dataclass
class CodexRunResult:
    success: bool
    submission_path: Path | None = None
    final_message_path: Path | None = None
    stdout_path: Path | None = None
    stderr_path: Path | None = None
    prompt_path: Path | None = None
    issues: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    return_code: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "submission_path": str(self.submission_path) if self.submission_path else None,
            "final_message_path": str(self.final_message_path) if self.final_message_path else None,
            "stdout_path": str(self.stdout_path) if self.stdout_path else None,
            "stderr_path": str(self.stderr_path) if self.stderr_path else None,
            "prompt_path": str(self.prompt_path) if self.prompt_path else None,
            "issues": self.issues,
            "notes": self.notes,
            "return_code": self.return_code,
        }


class SkillRunner:
    """Run a validated skill with Codex CLI and collect its JSON claim."""

    def call_skill_runner(self, request: CodexRunRequest) -> CodexRunResult:
        request.run_dir.mkdir(parents=True, exist_ok=True)

        prompt_path = request.run_dir / "prompt.md"
        final_message_path = request.run_dir / "codex.final-message.txt"
        stdout_path = request.run_dir / "codex.stdout.log"
        stderr_path = request.run_dir / "codex.stderr.log"
        submission_path = request.run_dir / "submission.json"
        metadata_path = request.run_dir / "runner_metadata.json"

        prompt_text = build_prompt(request)
        prompt_path.write_text(prompt_text, encoding="utf-8")

        launch = prepare_windows_codex_launch(CODEX_COMMAND)
        command = [launch.command, "--sandbox", CODEX_SANDBOX_MODE]
        if ENABLE_CODEX_SEARCH:
            command.append("--search")
        command.extend(["exec", "--output-last-message", str(final_message_path), "-"])

        try:
            completed = subprocess.run(
                command,
                cwd=INNO_ROOT,
                env=launch.env,
                input=prompt_text,
                text=True,
                capture_output=True,
                check=False,
                timeout=CODEX_TIMEOUT_SECONDS,
            )
        except FileNotFoundError as exc:
            issue = f"Codex CLI command was not found: {exc}"
            stderr_path.write_text(issue + "\n", encoding="utf-8")
            _write_metadata(metadata_path, request, launch.notes, None)
            return CodexRunResult(False, None, final_message_path, stdout_path, stderr_path, prompt_path, [issue], launch.notes)
        except subprocess.TimeoutExpired as exc:
            issue = f"Codex CLI timed out after {CODEX_TIMEOUT_SECONDS} seconds."
            stdout_path.write_text(exc.stdout or "", encoding="utf-8")
            stderr_path.write_text((exc.stderr or "") + "\n" + issue + "\n", encoding="utf-8")
            _write_metadata(metadata_path, request, launch.notes, None)
            return CodexRunResult(False, None, final_message_path, stdout_path, stderr_path, prompt_path, [issue], launch.notes)

        stdout_path.write_text(completed.stdout, encoding="utf-8")
        stderr_path.write_text(completed.stderr, encoding="utf-8")
        _write_metadata(metadata_path, request, launch.notes, completed.returncode)

        if completed.returncode != 0:
            return CodexRunResult(
                success=False,
                final_message_path=final_message_path,
                stdout_path=stdout_path,
                stderr_path=stderr_path,
                prompt_path=prompt_path,
                issues=[f"Codex CLI exited with code {completed.returncode}."],
                notes=launch.notes,
                return_code=completed.returncode,
            )

        response_text = final_message_path.read_text(encoding="utf-8") if final_message_path.exists() else completed.stdout
        try:
            submission = extract_json_object(response_text)
            validation_issues = validate_submission_contract(submission, request.public_data_dir)
        except ValueError as exc:
            return CodexRunResult(
                success=False,
                final_message_path=final_message_path,
                stdout_path=stdout_path,
                stderr_path=stderr_path,
                prompt_path=prompt_path,
                issues=[str(exc)],
                notes=launch.notes,
                return_code=completed.returncode,
            )

        if validation_issues:
            return CodexRunResult(
                success=False,
                final_message_path=final_message_path,
                stdout_path=stdout_path,
                stderr_path=stderr_path,
                prompt_path=prompt_path,
                issues=validation_issues,
                notes=launch.notes,
                return_code=completed.returncode,
            )

        submission_path.write_text(json.dumps(submission, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return CodexRunResult(
            success=True,
            submission_path=submission_path,
            final_message_path=final_message_path,
            stdout_path=stdout_path,
            stderr_path=stderr_path,
            prompt_path=prompt_path,
            notes=launch.notes,
            return_code=completed.returncode,
        )


def build_prompt(request: CodexRunRequest) -> str:
    skill_md_path = request.skill_dir / "SKILL.md"
    skill_text = skill_md_path.read_text(encoding="utf-8")
    public_files = ", ".join(path.name for path in sorted(request.public_data_dir.iterdir()) if path.is_file())
    platform_section = ""
    launch = prepare_windows_codex_launch(CODEX_COMMAND)
    if launch.prompt_guidance:
        platform_section = f"\nPlatform-specific guidance:\n{launch.prompt_guidance}\n"

    return f"""You are Codex CLI running a Fantasy Cup skill execution.

Execute the submitted skill using only the local public data snapshot and schema
listed below. Return only the final team submission JSON object; do not wrap it
in markdown fences and do not include commentary.

Run context:
- Validation job id: {request.job_id}
- Team id from upload form: {request.team_id or "not-provided"}
- Skill name: {request.skill_name or request.skill_dir.name}
- Skill folder: {request.skill_dir}
- Public data folder: {request.public_data_dir}
- Submission schema: {request.schema_path}
- Public files available: {public_files}
{platform_section}
Output contract:
- Return exactly one JSON object.
- The object must have `team_id`, `team_name`, `matchday_id`, and `answers`.
- Use the upload team id `{request.team_id or "not-provided"}` as `team_id` when it is provided.
- `answers.fantasy_xi` must contain exactly 11 entries.
- Every Fantasy XI entry must use this shape: {{ "record_id": "match_id:player_id" }}.
- Every `record_id` must be present in `players.json`.
- `answers.risk_play` must be `null` or a valid risk claim object from `risk_claims.json`.
- `answers.strategy_summary` must be a non-empty string.

Submitted skill:
{skill_text}
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


def validate_submission_contract(submission: dict[str, Any], public_data_dir: Path) -> list[str]:
    issues: list[str] = []
    for key in ("team_id", "team_name", "matchday_id", "answers"):
        if key not in submission:
            issues.append(f"Submission is missing required field: {key}")

    answers = submission.get("answers")
    if not isinstance(answers, dict):
        return [*issues, "Submission field `answers` must be an object."]

    fantasy_xi = answers.get("fantasy_xi")
    if not isinstance(fantasy_xi, list):
        issues.append("answers.fantasy_xi must be a list.")
    elif len(fantasy_xi) != 11:
        issues.append("answers.fantasy_xi must contain exactly 11 entries.")
    else:
        valid_record_ids = _load_public_record_ids(public_data_dir)
        for index, entry in enumerate(fantasy_xi, start=1):
            record_id = _record_id_from_entry(entry)
            if not record_id:
                issues.append(f"answers.fantasy_xi[{index}] must contain a record_id.")
            elif valid_record_ids and record_id not in valid_record_ids:
                issues.append(f"answers.fantasy_xi[{index}] record_id is not present in players.json: {record_id}")

    if "strategy_summary" not in answers or not str(answers.get("strategy_summary") or "").strip():
        issues.append("answers.strategy_summary must be a non-empty string.")
    if "risk_play" not in answers:
        issues.append("answers.risk_play must be present; use null when skipping Risk Play.")

    return issues


def _record_id_from_entry(entry: Any) -> str | None:
    if isinstance(entry, str):
        return entry
    if isinstance(entry, dict):
        record_id = entry.get("record_id")
        if isinstance(record_id, str):
            return record_id
    return None


def _load_public_record_ids(public_data_dir: Path) -> set[str]:
    players_path = public_data_dir / "players.json"
    if not players_path.is_file():
        return set()
    try:
        players = json.loads(players_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return set()
    if not isinstance(players, list):
        return set()
    return {player["record_id"] for player in players if isinstance(player, dict) and isinstance(player.get("record_id"), str)}


def _write_metadata(metadata_path: Path, request: CodexRunRequest, notes: list[str], return_code: int | None) -> None:
    metadata_path.write_text(
        json.dumps(
            {
                "job_id": request.job_id,
                "team_id": request.team_id,
                "skill_name": request.skill_name,
                "skill_dir": str(request.skill_dir),
                "public_data_dir": str(request.public_data_dir),
                "schema_path": str(request.schema_path),
                "codex_command": CODEX_COMMAND,
                "sandbox": CODEX_SANDBOX_MODE,
                "search_enabled": ENABLE_CODEX_SEARCH,
                "notes": notes,
                "return_code": return_code,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


# Backwards-compatible alias for the previous misspelled class name.
SkillRuner = SkillRunner
