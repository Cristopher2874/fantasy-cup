"""Static validation for uploaded Codex skill folders."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from services.validator.skill_guardrail import SkillGuardrail


MAX_SKILL_MD_BYTES = 250_000
MAX_SKILL_BODY_LINES = 500
SKILL_NAME_PATTERN = r"^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?$"
REQUIRED_FRONTMATTER_KEYS = frozenset({"name", "description"})
STRICT_FRONTMATTER_KEYS = True

# This validator intentionally excludes scripts because submitted skills are
# expected to be instruction/resource bundles, not executable packages.
ALLOWED_TOP_LEVEL_NAMES = frozenset({"SKILL.md", "agents", "references", "assets"})
OPTIONAL_RESOURCE_DIRS = frozenset({"agents", "references", "assets"})
FORBIDDEN_DIR_NAMES = frozenset({"scripts", "bin", "cmd", "commands", ".git", ".github"})
SCRIPT_OR_EXECUTABLE_EXTENSIONS = frozenset(
    {
        ".app",
        ".bat",
        ".bin",
        ".cmd",
        ".com",
        ".cpl",
        ".dll",
        ".exe",
        ".gadget",
        ".jar",
        ".js",
        ".jse",
        ".mjs",
        ".msi",
        ".php",
        ".pl",
        ".ps1",
        ".psm1",
        ".py",
        ".pyc",
        ".pyo",
        ".pyw",
        ".rb",
        ".scr",
        ".sh",
        ".ts",
        ".vb",
        ".vbe",
        ".vbs",
        ".ws",
        ".wsf",
    }
)
EXECUTABLE_MAGIC_PREFIXES = (
    b"MZ",
    b"\x7fELF",
    b"\xca\xfe\xba\xbe",
    b"\xfe\xed\xfa",
    b"\xce\xfa\xed",
)


@dataclass
class SkillValidationReport:
    source_path: Path
    skill_name: str | None = None
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    guardrail_ran: bool = False

    @property
    def is_valid(self) -> bool:
        return not self.errors


class SkillValidator:
    def __init__(self, guardrail: SkillGuardrail | None = None):
        self._guardrail = guardrail or SkillGuardrail()

    def validate_skill(self, skill_root: Path, require_folder_name: bool = True) -> SkillValidationReport:
        report = SkillValidationReport(source_path=skill_root)

        self._validate_case_normalized_paths(skill_root, report)
        self._validate_folder_structure(skill_root, require_folder_name, report)
        self._validate_no_scripts_or_executables(skill_root, report)
        if not report.is_valid:
            return report

        report.guardrail_ran = True
        guardrail_decision = self._guardrail.validate_with_guardrail(skill_root)
        if not guardrail_decision.valid:
            report.errors.extend(f"LLM guardrail: {issue}" for issue in guardrail_decision.issues)

        return report

    def _validate_case_normalized_paths(self, skill_root: Path, report: SkillValidationReport) -> None:
        if not skill_root.exists():
            report.errors.append(f"Skill folder does not exist: {skill_root}")
            return

        seen_paths: dict[str, str] = {}
        for path in skill_root.rglob("*"):
            relative_path = path.relative_to(skill_root).as_posix()
            normalized = relative_path.casefold()
            previous = seen_paths.get(normalized)
            if previous and previous != relative_path:
                report.errors.append(f"Case-insensitive duplicate paths: {previous} and {relative_path}")
            else:
                seen_paths[normalized] = relative_path

    def _validate_folder_structure(
        self,
        skill_root: Path,
        require_folder_name: bool,
        report: SkillValidationReport,
    ) -> None:
        skill_root = skill_root.resolve()
        report.source_path = skill_root

        if not skill_root.exists():
            report.errors.append(f"Skill folder does not exist: {skill_root}")
            return
        if not skill_root.is_dir():
            report.errors.append(f"Skill path must be a folder: {skill_root}")
            return

        skill_md = _exact_child(skill_root, "SKILL.md")
        if skill_md is None:
            if any(child.name.casefold() == "skill.md" for child in skill_root.iterdir()):
                report.errors.append("SKILL.md must be named exactly SKILL.md.")
            else:
                report.errors.append("Missing required SKILL.md file.")
            return

        if not skill_md.is_file():
            report.errors.append("SKILL.md must be a file.")
            return
        if skill_md.stat().st_size > MAX_SKILL_MD_BYTES:
            report.errors.append(f"SKILL.md is larger than {MAX_SKILL_MD_BYTES} bytes.")
            return

        try:
            skill_text = skill_md.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            report.errors.append("SKILL.md must be UTF-8 text.")
            return

        frontmatter, body, parse_errors = _parse_frontmatter(skill_text)
        report.errors.extend(parse_errors)
        if parse_errors:
            return

        self._validate_frontmatter(frontmatter, body, skill_root, require_folder_name, report)
        self._validate_top_level_entries(skill_root, report)

    def _validate_frontmatter(
        self,
        frontmatter: dict[str, str],
        body: str,
        skill_root: Path,
        require_folder_name: bool,
        report: SkillValidationReport,
    ) -> None:
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
        elif require_folder_name and skill_root.name != skill_name:
            report.errors.append(f"Skill folder name must match frontmatter name: expected {skill_name}, got {skill_root.name}")

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

    def _validate_top_level_entries(self, skill_root: Path, report: SkillValidationReport) -> None:
        for entry in sorted(skill_root.iterdir(), key=lambda path: path.name.lower()):
            if entry.name not in ALLOWED_TOP_LEVEL_NAMES:
                report.errors.append(
                    f"Unexpected top-level entry {entry.name}; allowed entries are SKILL.md, agents, references, assets."
                )
                continue

            if entry.name == "SKILL.md":
                if not entry.is_file():
                    report.errors.append("SKILL.md must be a file.")
                continue

            if entry.name in OPTIONAL_RESOURCE_DIRS and not entry.is_dir():
                report.errors.append(f"{entry.name} must be a directory when present.")

    def _validate_no_scripts_or_executables(self, skill_root: Path, report: SkillValidationReport) -> None:
        if not skill_root.exists() or not skill_root.is_dir():
            return

        for path in sorted(skill_root.rglob("*"), key=lambda item: item.as_posix().lower()):
            relative_path = path.relative_to(skill_root).as_posix()
            if path.is_dir():
                if path.name.casefold() in FORBIDDEN_DIR_NAMES:
                    report.errors.append(f"Directory is not allowed in a skill upload: {relative_path}")
                continue

            suffix = path.suffix.casefold()
            if suffix in SCRIPT_OR_EXECUTABLE_EXTENSIONS:
                report.errors.append(f"Scripts and executables are not allowed: {relative_path}")
                continue

            if path.stat().st_mode & 0o111:
                report.errors.append(f"Executable file permissions are not allowed: {relative_path}")
                continue

            if _file_starts_with_shebang(path):
                report.errors.append(f"Shebang scripts are not allowed: {relative_path}")
                continue

            if _file_has_executable_magic(path):
                report.errors.append(f"Executable binary content is not allowed: {relative_path}")


def _exact_child(parent: Path, child_name: str) -> Path | None:
    for child in parent.iterdir():
        if child.name == child_name:
            return child
    return None


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


def _file_starts_with_shebang(path: Path) -> bool:
    try:
        with path.open("rb") as file:
            return file.read(2) == b"#!"
    except OSError:
        return False


def _file_has_executable_magic(path: Path) -> bool:
    try:
        with path.open("rb") as file:
            prefix = file.read(8)
    except OSError:
        return False
    return any(prefix.startswith(magic) for magic in EXECUTABLE_MAGIC_PREFIXES)
