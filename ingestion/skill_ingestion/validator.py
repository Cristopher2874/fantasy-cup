from __future__ import annotations

import re
from pathlib import Path

from .config import (
    ALLOWED_TOP_LEVEL_NAMES,
    MAX_SKILL_BODY_LINES,
    MAX_SKILL_MD_BYTES,
    OPTIONAL_RESOURCE_DIRS,
    REQUIRED_FRONTMATTER_KEYS,
    SKILL_NAME_PATTERN,
    STRICT_FRONTMATTER_KEYS,
)
from .models import ValidationReport


def validate_skill_folder(skill_dir: Path, require_folder_name: bool = True) -> ValidationReport:
    skill_dir = skill_dir.resolve()
    report = ValidationReport(source_path=skill_dir)

    if not skill_dir.exists():
        report.errors.append(f"Skill folder does not exist: {skill_dir}")
        return report
    if not skill_dir.is_dir():
        report.errors.append(f"Skill path must be a folder: {skill_dir}")
        return report

    skill_md = skill_dir / "SKILL.md"
    if not skill_md.is_file():
        report.errors.append("Missing required SKILL.md file.")
        return report
    if skill_md.stat().st_size > MAX_SKILL_MD_BYTES:
        report.errors.append(f"SKILL.md is larger than {MAX_SKILL_MD_BYTES} bytes.")
        return report

    try:
        skill_text = skill_md.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        report.errors.append("SKILL.md must be UTF-8 text.")
        return report

    frontmatter, body, parse_errors = _parse_frontmatter(skill_text)
    report.errors.extend(parse_errors)
    if parse_errors:
        return report

    missing_keys = sorted(REQUIRED_FRONTMATTER_KEYS - frontmatter.keys())
    for key in missing_keys:
        report.errors.append(f"SKILL.md frontmatter is missing required field: {key}")

    extra_keys = sorted(frontmatter.keys() - REQUIRED_FRONTMATTER_KEYS)
    for key in extra_keys:
        message = f"SKILL.md frontmatter should only contain name and description; found: {key}"
        if STRICT_FRONTMATTER_KEYS:
            report.errors.append(message)
        else:
            report.warnings.append(message)

    skill_name = frontmatter.get("name", "").strip()
    report.skill_name = skill_name or None
    if not skill_name:
        report.errors.append("SKILL.md frontmatter field name must be non-empty.")
    elif not re.fullmatch(SKILL_NAME_PATTERN, skill_name):
        report.errors.append("Skill name must use lowercase letters, digits, and hyphens, and be under 64 characters.")
    elif require_folder_name and skill_dir.name != skill_name:
        report.errors.append(f"Skill folder name must match frontmatter name: expected {skill_name}, got {skill_dir.name}")

    description = frontmatter.get("description", "").strip()
    if not description:
        report.errors.append("SKILL.md frontmatter field description must be non-empty.")
    elif len(description) < 20:
        report.warnings.append("Description is very short; include what the skill does and when to use it.")
    elif len(description) > 1_000:
        report.warnings.append("Description is long; keep trigger metadata concise.")

    if not body.strip():
        report.errors.append("SKILL.md body must contain instructions.")
    elif len(body.splitlines()) > MAX_SKILL_BODY_LINES:
        report.warnings.append(f"SKILL.md body is longer than {MAX_SKILL_BODY_LINES} lines; prefer references for details.")

    _validate_top_level_entries(skill_dir, report)
    return report


def _validate_top_level_entries(skill_dir: Path, report: ValidationReport) -> None:
    for entry in sorted(skill_dir.iterdir(), key=lambda path: path.name.lower()):
        if entry.name not in ALLOWED_TOP_LEVEL_NAMES:
            report.errors.append(
                f"Unexpected top-level entry {entry.name}; allowed entries are SKILL.md, agents, scripts, references, assets."
            )
            continue

        if entry.name == "SKILL.md":
            if not entry.is_file():
                report.errors.append("SKILL.md must be a file.")
            continue

        if entry.name in OPTIONAL_RESOURCE_DIRS and not entry.is_dir():
            report.errors.append(f"{entry.name} must be a directory when present.")


def _parse_frontmatter(skill_text: str) -> tuple[dict[str, str], str, list[str]]:
    skill_text = skill_text.lstrip("\ufeff")
    lines = skill_text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, skill_text, ["SKILL.md must start with YAML frontmatter delimited by ---."]

    closing_index: int | None = None
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            closing_index = index
            break

    if closing_index is None:
        return {}, "", ["SKILL.md frontmatter is missing the closing --- delimiter."]

    frontmatter_lines = lines[1:closing_index]
    body = "\n".join(lines[closing_index + 1 :])
    fields, errors = _parse_simple_yaml_fields(frontmatter_lines)
    return fields, body, errors


def _parse_simple_yaml_fields(lines: list[str]) -> tuple[dict[str, str], list[str]]:
    fields: dict[str, str] = {}
    errors: list[str] = []
    current_block_key: str | None = None
    current_block_lines: list[str] = []

    def flush_block() -> None:
        nonlocal current_block_key, current_block_lines
        if current_block_key is not None:
            fields[current_block_key] = " ".join(line.strip() for line in current_block_lines).strip()
            current_block_key = None
            current_block_lines = []

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        if current_block_key and (line.startswith(" ") or line.startswith("\t")):
            current_block_lines.append(line)
            continue

        flush_block()
        match = re.fullmatch(r"([A-Za-z_][A-Za-z0-9_-]*):(?:\s*(.*))?", line)
        if not match:
            errors.append(f"Unsupported frontmatter line: {line}")
            continue

        key = match.group(1)
        value = (match.group(2) or "").strip()
        if key in fields:
            errors.append(f"Duplicate frontmatter field: {key}")
            continue

        if value in {"|", ">"}:
            current_block_key = key
            current_block_lines = []
        else:
            fields[key] = _strip_yaml_quotes(value)

    flush_block()
    return fields, errors


def _strip_yaml_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value
