"""Upload endpoint for skill zip validation."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from services.validator.main_validator import ValidationBatchError, run_validator


router = APIRouter(tags=["upload"])


@router.post("/upload")
async def upload_skill(
    file_uploads: Annotated[list[UploadFile] | None, File(alias="file")] = None,
    files_uploads: Annotated[list[UploadFile] | None, File(alias="files")] = None,
    team_id: Annotated[str | None, Form()] = None,
) -> dict:
    uploads = [*(file_uploads or []), *(files_uploads or [])]
    try:
        return await run_validator(uploads, team_id=team_id)
    except ValidationBatchError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
