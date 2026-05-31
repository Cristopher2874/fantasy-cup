"""Upload endpoint for skill zip validation."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile

from services.pipeline import enqueue_validated_skill, run_pipeline_job
from services.validator.main_validator import ValidationBatchError, run_validator


router = APIRouter(tags=["upload"])


@router.post("/upload")
async def upload_skill(
    background_tasks: BackgroundTasks,
    file_uploads: Annotated[list[UploadFile] | None, File(alias="file")] = None,
    files_uploads: Annotated[list[UploadFile] | None, File(alias="files")] = None,
    team_id: Annotated[str | None, Form()] = None,
) -> dict:
    uploads = [*(file_uploads or []), *(files_uploads or [])]
    try:
        response = await run_validator(uploads, team_id=team_id)
    except ValidationBatchError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    for result in response["results"]:
        if not result.get("ready_for_dispatch"):
            continue
        pipeline_job = enqueue_validated_skill(
            validation_job_id=result["job_id"],
            team_id=team_id,
            skill_name=result.get("skill_name"),
            filename=result.get("filename"),
        )
        result["execution_job_id"] = pipeline_job.job_id
        result["execution_status"] = pipeline_job.status
        background_tasks.add_task(run_pipeline_job, pipeline_job.job_id)

    if any(result.get("execution_job_id") for result in response["results"]):
        response["execution_status"] = "queued"
    return response
