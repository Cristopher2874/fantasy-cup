from __future__ import annotations

import os
import platform
import shutil
from dataclasses import dataclass, field
from pathlib import Path


WINDOWS_FILE_ACCESS_GUIDANCE = """This run is using Windows Codex CLI workarounds.

When reading local files, use simple read-only PowerShell commands only:
- `Get-ChildItem -Force .\\team_submission\\public_data`
- `Get-Content -Raw -LiteralPath '.\\team_submission\\public_data\\manifest.json'`
- `Get-Content -Raw -LiteralPath '.\\team_submission\\public_data\\matchday.json'`
- `Get-Content -Raw -LiteralPath '.\\team_submission\\public_data\\players.json'`
- `Get-Content -Raw -LiteralPath '.\\team_submission\\public_data\\risk_claims.json'`
- `Get-Content -Raw -LiteralPath '.\\team_submission\\public_data\\answer_template.json'`
- `Get-Content -Raw -LiteralPath '.\\team_submission\\schemas\\team_submission.schema.json'`

Avoid compound PowerShell scripts, variables, loops, pipelines, ConvertFrom-Json,
Join-Path, redirection, Python, Node, or commands that would require approval.
If Windows sandbox setup fails before a command starts, report the failure rather
than guessing local `record_id` values from web search."""


@dataclass(frozen=True)
class WindowsCodexLaunch:
    command: str
    env: dict[str, str]
    notes: list[str] = field(default_factory=list)
    prompt_guidance: str = WINDOWS_FILE_ACCESS_GUIDANCE


def _standalone_codex_command() -> str | None:
    releases_dir = Path.home() / ".codex" / "packages" / "standalone" / "releases"
    if not releases_dir.exists():
        return None

    commands = [path for path in releases_dir.glob("*/bin/codex.exe") if path.exists()]
    if not commands:
        return None

    return str(max(commands, key=lambda path: path.stat().st_mtime))


def _path_key(env: dict[str, str]) -> str:
    for key in env:
        if key.lower() == "path":
            return key
    return "PATH"


def _force_path_front(env: dict[str, str], directory: Path) -> bool:
    path_key = _path_key(env)
    current_path = env.get(path_key, "")
    raw_entries = [item for item in current_path.split(os.pathsep) if item]
    normalized_target = str(directory.resolve()).casefold()

    kept_entries = []
    changed = False
    for raw_entry in raw_entries:
        entry = Path(raw_entry)
        try:
            if str(entry.resolve()).casefold() == normalized_target:
                changed = True
                continue
        except OSError:
            pass
        kept_entries.append(raw_entry)

    new_path = os.pathsep.join([str(directory), *kept_entries])
    if new_path != current_path:
        env[path_key] = new_path
        return True
    return changed


def _windows_helper_candidates(codex_dir: Path) -> list[Path]:
    helper_name = "codex-windows-sandbox-setup.exe"
    candidates = [
        codex_dir / helper_name,
        codex_dir.parent / "codex-resources" / helper_name,
        codex_dir.parent / "resources" / helper_name,
    ]

    releases_dir = Path.home() / ".codex" / "packages" / "standalone" / "releases"
    if releases_dir.exists():
        candidates.extend(sorted(releases_dir.glob(f"*/codex-resources/{helper_name}")))
        candidates.extend(sorted(releases_dir.glob(f"*/bin/{helper_name}")))

    unique = []
    seen = set()
    for candidate in candidates:
        key = str(candidate).casefold()
        if key not in seen:
            seen.add(key)
            unique.append(candidate)
    return unique


def _find_windows_helper(codex_dir: Path) -> Path | None:
    for candidate in _windows_helper_candidates(codex_dir):
        if candidate.exists():
            return candidate.resolve()
    return None


def prepare_windows_codex_launch(command: str) -> WindowsCodexLaunch:
    env = dict(os.environ)
    notes: list[str] = []

    if platform.system() != "Windows":
        resolved = shutil.which(command) or command
        notes.append("Windows workarounds requested on a non-Windows host; using normal command resolution.")
        return WindowsCodexLaunch(command=resolved, env=env, notes=notes, prompt_guidance="")

    resolved = _standalone_codex_command() or shutil.which(command) or command
    command_path = Path(resolved)
    codex_dir = command_path.parent.resolve() if command_path.parent != Path(".") else None

    if codex_dir:
        if _force_path_front(env, codex_dir):
            notes.append(f"Forced Codex bin directory to front of PATH: {codex_dir}")

        helper_path = _find_windows_helper(codex_dir)
        if helper_path:
            helper_dir = helper_path.parent
            if _force_path_front(env, helper_dir):
                notes.append(f"Forced Codex resources directory to front of PATH: {helper_dir}")
            notes.append(f"Windows sandbox helper: {helper_path}")
        else:
            checked = ", ".join(str(path) for path in _windows_helper_candidates(codex_dir)[:4])
            notes.append(f"Windows sandbox helper was not found. Checked: {checked}")
    else:
        notes.append("Could not resolve Codex install directory for Windows PATH workaround.")

    return WindowsCodexLaunch(command=resolved, env=env, notes=notes)
