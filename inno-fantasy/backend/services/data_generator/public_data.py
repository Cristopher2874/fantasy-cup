"""Public data snapshot creation for Codex skill runs."""
from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path


PUBLIC_DATA_FILES = (
    "manifest.json",
    "matchday.json",
    "matches.json",
    "teams.json",
    "players.json",
    "risk_claims.json",
    "answer_template.json",
    "public_data_catalog.md",
)


@dataclass(frozen=True)
class PublicDataSnapshot:
    public_data_dir: Path
    schema_path: Path
    files: list[Path]


def create_public_data_snapshot(run_dir: Path, source_public_data_dir: Path, source_schema_path: Path) -> PublicDataSnapshot:
    """Copy the generated public-data artifact bundle into the immutable run folder."""
    if not source_public_data_dir.is_dir():
        raise FileNotFoundError(f"Public data directory does not exist: {source_public_data_dir}")
    if not source_schema_path.is_file():
        raise FileNotFoundError(f"Submission schema does not exist: {source_schema_path}")

    public_data_dir = run_dir / "public_data"
    schema_dir = run_dir / "schemas"
    schema_path = schema_dir / "team_submission.schema.json"
    public_data_dir.mkdir(parents=True, exist_ok=True)
    schema_dir.mkdir(parents=True, exist_ok=True)

    copied_files: list[Path] = []
    for filename in PUBLIC_DATA_FILES:
        source_path = source_public_data_dir / filename
        if not source_path.is_file():
            raise FileNotFoundError(f"Public data file does not exist: {source_path}")
        destination_path = public_data_dir / filename
        shutil.copy2(source_path, destination_path)
        copied_files.append(destination_path)

    shutil.copy2(source_schema_path, schema_path)
    return PublicDataSnapshot(public_data_dir=public_data_dir, schema_path=schema_path, files=[*copied_files, schema_path])
