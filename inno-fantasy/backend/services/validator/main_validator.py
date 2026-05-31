"""Orchestrates the complete uploaded-skill validation flow."""
from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from services.validator.skill_validator import SkillValidator
from services.validator.zip_handler import MAX_UPLOADS, ExtractedSkill, ZipHandler


_VALIDATED_SKILL_PATHS: dict[str, Path] = {}


class ValidationBatchError(ValueError):
    """Raised when the upload request itself cannot be processed."""


@dataclass
class ValidationResult:
    job_id: str
    filename: str
    valid: bool
    status: str
    issues: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    skill_name: str | None = None
    ready_for_dispatch: bool = False
    validated_path: Path | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "filename": self.filename,
            "valid": self.valid,
            "status": self.status,
            "skill_name": self.skill_name,
            "issues": self.issues,
            "warnings": self.warnings,
            "ready_for_dispatch": self.ready_for_dispatch,
        }


async def run_validator(files: Any, team_id: str | None = None) -> dict[str, Any]:
    """Validate up to five uploaded skill zip files and return per-file results."""
    uploads = _normalize_uploads(files)
    if not uploads:
        raise ValidationBatchError("Upload at least one zip file.")
    if len(uploads) > MAX_UPLOADS:
        raise ValidationBatchError(f"Upload at most {MAX_UPLOADS} zip files at a time.")

    batch_job_id = uuid.uuid4().hex
    semaphore = asyncio.Semaphore(MAX_UPLOADS)

    async def validate_with_limit(upload_file: Any) -> ValidationResult:
        async with semaphore:
            return await _validate_one_upload(upload_file)

    results = await asyncio.gather(*(validate_with_limit(upload) for upload in uploads))
    accepted = sum(1 for result in results if result.valid)
    rejected = len(results) - accepted

    return {
        "job_id": batch_job_id,
        "team_id": team_id,
        "status": "valid" if rejected == 0 else "invalid",
        "accepted": accepted,
        "rejected": rejected,
        "results": [result.to_dict() for result in results],
    }


async def _validate_one_upload(upload_file: Any) -> ValidationResult:
    job_id = uuid.uuid4().hex
    zip_handler = ZipHandler()
    staged_zip: ExtractedSkill | None = None

    try:
        staged_zip = await zip_handler.handle_uploaded_zip(upload_file, job_id)
        filename = staged_zip.original_filename
        issues = list(staged_zip.errors)
        warnings = list(staged_zip.warnings)
        skill_name: str | None = None
        validated_path: Path | None = None

        if not issues and staged_zip.skill_root is not None:
            skill_report = await asyncio.to_thread(
                _validate_skill_folder,
                staged_zip.skill_root,
                staged_zip.require_folder_name,
            )
            issues.extend(skill_report.errors)
            warnings.extend(skill_report.warnings)
            skill_name = skill_report.skill_name
            if skill_report.is_valid:
                validated_path = staged_zip.skill_root

        valid = not issues
        if not valid and staged_zip is not None:
            staged_zip.cleanup()
        elif valid and validated_path is not None:
            _VALIDATED_SKILL_PATHS[job_id] = validated_path

        return ValidationResult(
            job_id=job_id,
            filename=filename,
            valid=valid,
            status="valid" if valid else "invalid",
            issues=_dedupe(issues),
            warnings=_dedupe(warnings),
            skill_name=skill_name,
            ready_for_dispatch=valid,
            validated_path=validated_path,
        )
    except Exception as exc:  # pragma: no cover - keeps batch response stable
        if staged_zip is not None:
            staged_zip.cleanup()
        filename = getattr(upload_file, "filename", "unknown.zip") or "unknown.zip"
        return ValidationResult(
            job_id=job_id,
            filename=filename,
            valid=False,
            status="invalid",
            issues=[f"Unexpected validation error: {exc}"],
        )


def _validate_skill_folder(skill_root: Path, require_folder_name: bool):
    return SkillValidator().validate_skill(skill_root, require_folder_name=require_folder_name)


def get_validated_skill_path(job_id: str) -> Path | None:
    """Resolve a validated upload job to its staged skill path for dispatch."""
    return _VALIDATED_SKILL_PATHS.get(job_id)


def _normalize_uploads(files: Any) -> list[Any]:
    if files is None:
        return []
    if isinstance(files, (str, bytes)):
        return [files]
    if isinstance(files, Iterable):
        return [file for file in files if file is not None]
    return [files]


def _dedupe(items: list[str]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        deduped.append(item)
    return deduped
