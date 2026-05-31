"""Skill execution pipeline.

Validated uploads are queued here, snapshotted into a run folder, and executed
one-by-one with the Codex CLI runner.
"""
from __future__ import annotations

import asyncio
import json
import shutil
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from services.codex_runner.skill_runner import CodexRunRequest, SkillRunner
from services.data_generator.public_data import create_public_data_snapshot
from services.validator.main_validator import get_validated_skill_path, release_validated_skill


BACKEND_ROOT = Path(__file__).resolve().parents[1]
INNO_ROOT = BACKEND_ROOT.parent
RUNS_ROOT = INNO_ROOT / "data" / "runs"
PUBLIC_DATA_SOURCE_DIR = INNO_ROOT / "data" / "public_data"
SUBMISSION_SCHEMA_PATH = BACKEND_ROOT / "models" / "team_submission.schema.json"

STATUS_QUEUED = "queued"
STATUS_RUNNING = "running"
STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"

_PIPELINE_JOBS: dict[str, "PipelineJob"] = {}
_PIPELINE_LOCK = asyncio.Lock()


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass
class PipelineJob:
    job_id: str
    validation_job_id: str
    team_id: str | None
    skill_name: str | None
    filename: str | None
    status: str = STATUS_QUEUED
    stage: str = "queued"
    message: str = "Skill is queued for Codex execution."
    created_at: str = field(default_factory=_utc_now)
    updated_at: str = field(default_factory=_utc_now)
    run_dir: Path | None = None
    submission_path: Path | None = None
    issues: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    runner: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "validation_job_id": self.validation_job_id,
            "team_id": self.team_id,
            "skill_name": self.skill_name,
            "filename": self.filename,
            "status": self.status,
            "stage": self.stage,
            "message": self.message,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "run_dir": str(self.run_dir) if self.run_dir else None,
            "submission_path": str(self.submission_path) if self.submission_path else None,
            "issues": self.issues,
            "warnings": self.warnings,
            "runner": self.runner,
        }


def enqueue_validated_skill(
    validation_job_id: str,
    team_id: str | None,
    skill_name: str | None = None,
    filename: str | None = None,
) -> PipelineJob:
    """Queue a validator-approved skill for Codex execution."""
    staged_skill_path = get_validated_skill_path(validation_job_id)
    if staged_skill_path is None:
        raise ValueError(f"No validated skill is registered for job id: {validation_job_id}")

    existing = _PIPELINE_JOBS.get(validation_job_id)
    if existing is not None:
        return existing

    job = PipelineJob(
        job_id=validation_job_id,
        validation_job_id=validation_job_id,
        team_id=team_id,
        skill_name=skill_name,
        filename=filename,
    )
    _PIPELINE_JOBS[job.job_id] = job
    return job


async def run_pipeline_job(job_id: str) -> PipelineJob:
    """Run a queued job. A process-local lock keeps Codex executions one-by-one."""
    async with _PIPELINE_LOCK:
        job = _get_existing_job(job_id)
        if job.status == STATUS_COMPLETED:
            return job
        if job.status == STATUS_RUNNING:
            return job
        return await asyncio.to_thread(_run_pipeline_job_sync, job.job_id)


def get_pipeline_job(job_id: str) -> dict[str, Any] | None:
    job = _PIPELINE_JOBS.get(job_id)
    return job.to_dict() if job else None


def list_pipeline_jobs() -> list[dict[str, Any]]:
    return [job.to_dict() for job in sorted(_PIPELINE_JOBS.values(), key=lambda item: item.created_at, reverse=True)]


def run_skill_pipeline(validation_job_id: str, team_id: str | None = None) -> dict[str, Any]:
    """Compatibility wrapper for older callers that want a blocking run."""
    job = enqueue_validated_skill(validation_job_id, team_id=team_id)
    result = _run_pipeline_job_sync(job.job_id)
    return result.to_dict()


def _run_pipeline_job_sync(job_id: str) -> PipelineJob:
    job = _get_existing_job(job_id)
    staged_skill_path = get_validated_skill_path(job.validation_job_id)
    if staged_skill_path is None:
        _mark_failed(job, "Validated skill files are no longer available for execution.")
        return job

    try:
        _update_job(job, status=STATUS_RUNNING, stage="snapshot", message="Creating immutable run snapshot.")
        run_dir = _new_run_dir(job)
        skill_snapshot_dir = run_dir / "skill"
        shutil.copytree(staged_skill_path, skill_snapshot_dir, dirs_exist_ok=True)
        release_validated_skill(job.validation_job_id)

        data_snapshot = create_public_data_snapshot(run_dir, PUBLIC_DATA_SOURCE_DIR, SUBMISSION_SCHEMA_PATH)
        job.run_dir = run_dir
        _write_job_state(job)

        _update_job(job, stage="codex", message="Running Codex CLI against the validated skill.")
        result = SkillRunner().call_skill_runner(
            CodexRunRequest(
                job_id=job.job_id,
                team_id=job.team_id,
                skill_name=job.skill_name,
                skill_dir=skill_snapshot_dir,
                public_data_dir=data_snapshot.public_data_dir,
                schema_path=data_snapshot.schema_path,
                run_dir=run_dir,
            )
        )

        job.runner = result.to_dict()
        if result.success:
            job.submission_path = result.submission_path
            _update_job(job, status=STATUS_COMPLETED, stage="completed", message="Codex execution completed.")
        else:
            job.issues.extend(result.issues)
            _update_job(job, status=STATUS_FAILED, stage="failed", message="Codex execution failed.")
        return job
    except Exception as exc:  # pragma: no cover - defensive boundary for background jobs
        _mark_failed(job, f"Pipeline execution failed: {exc}")
        return job


def _new_run_dir(job: PipelineJob) -> Path:
    skill_segment = _safe_segment(job.skill_name or job.filename or "skill")
    run_dir = RUNS_ROOT / job.job_id / skill_segment
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def _get_existing_job(job_id: str) -> PipelineJob:
    job = _PIPELINE_JOBS.get(job_id)
    if job is None:
        raise KeyError(f"Pipeline job not found: {job_id}")
    return job


def _update_job(job: PipelineJob, *, status: str | None = None, stage: str | None = None, message: str | None = None) -> None:
    if status is not None:
        job.status = status
    if stage is not None:
        job.stage = stage
    if message is not None:
        job.message = message
    job.updated_at = _utc_now()
    _write_job_state(job)


def _mark_failed(job: PipelineJob, issue: str) -> None:
    job.issues.append(issue)
    _update_job(job, status=STATUS_FAILED, stage="failed", message=issue)


def _write_job_state(job: PipelineJob) -> None:
    if job.run_dir is None:
        return
    state_path = job.run_dir / "pipeline_job.json"
    state_path.write_text(json.dumps(job.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _safe_segment(value: str) -> str:
    cleaned = "".join(char if char.isalnum() or char in {"-", "_"} else "-" for char in value.strip().lower())
    return cleaned.strip("-") or "skill"
