""" SSE event emiter that will inform the use rof the curren stage """

from pathlib import Path
import shutil

from fastapi import APIRouter, File, Header, HTTPException, UploadFile
from pydantic import BaseModel, Field

from backend.config import settings
from backend.services.pipeline import run_skill_pipeline
from schemas.models.payload_schemas import UploadSkillRequest

router = APIRouter(tags=["progress"])

@router.post("/progress")
def upload_skill(payload: UploadSkillRequest) -> dict:
    validator_response = run_skill_pipeline(payload.file)

    return {"status": validator_response.status, "job_id": validator_response.job_id}