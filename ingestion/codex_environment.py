from __future__ import annotations

import os
import platform
import shutil
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class CodexEnvironment:
    command: str
    env: dict[str, str]
    codex_dir: Path | None = None
    helper_path: Path | None = None
    path_fix_applied: bool = False
    path_entries_added: list[Path] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def resolve_command(command: str) -> str:
    found = shutil.which(command)
    if found:
        return found
    return command


def _path_key(env: dict[str, str]) -> str:
    for key in env:
        if key.lower() == "path":
            return key
    return "PATH"


def _prepend_path(env: dict[str, str], directory: Path) -> bool:
    path_key = _path_key(env)
    current_path = env.get(path_key, "")
    entries = [Path(item) for item in current_path.split(os.pathsep) if item]
    normalized_target = str(directory.resolve()).casefold()

    for entry in entries:
        try:
            if str(entry.resolve()).casefold() == normalized_target:
                return False
        except OSError:
            continue

    env[path_key] = f"{directory}{os.pathsep}{current_path}" if current_path else str(directory)
    return True


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

    unique_candidates: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate).casefold()
        if key not in seen:
            seen.add(key)
            unique_candidates.append(candidate)
    return unique_candidates


def _find_windows_helper(codex_dir: Path) -> Path | None:
    for candidate in _windows_helper_candidates(codex_dir):
        if candidate.exists():
            return candidate.resolve()
    return None


def prepare_codex_environment(command: str, path_fix: str = "auto") -> CodexEnvironment:
    if path_fix not in {"auto", "always", "off"}:
        raise ValueError("path_fix must be one of: auto, always, off")

    resolved_command = resolve_command(command)
    env = dict(os.environ)
    warnings: list[str] = []
    codex_dir: Path | None = None
    helper_path: Path | None = None
    path_fix_applied = False
    path_entries_added: list[Path] = []

    command_path = Path(resolved_command)
    if command_path.parent != Path("."):
        codex_dir = command_path.parent.resolve()

    should_apply = path_fix == "always" or (path_fix == "auto" and platform.system() == "Windows")
    if should_apply:
        if codex_dir:
            if _prepend_path(env, codex_dir):
                path_entries_added.append(codex_dir)
            if platform.system() == "Windows":
                helper_path = _find_windows_helper(codex_dir)
                if helper_path:
                    helper_dir = helper_path.parent
                    if _prepend_path(env, helper_dir):
                        path_entries_added.append(helper_dir)
                else:
                    checked = ", ".join(str(path) for path in _windows_helper_candidates(codex_dir)[:4])
                    warnings.append(f"Windows sandbox helper was not found. Checked: {checked}")
        else:
            warnings.append(
                "Could not resolve Codex install directory. Pass --codex-command with the full Codex executable path."
            )

    path_fix_applied = bool(path_entries_added)

    return CodexEnvironment(
        command=resolved_command,
        env=env,
        codex_dir=codex_dir,
        helper_path=helper_path,
        path_fix_applied=path_fix_applied,
        path_entries_added=path_entries_added,
        warnings=warnings,
    )
