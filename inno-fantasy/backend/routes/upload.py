""" endpoint to use for zip uploads """

#receive the uploaded zip

#generate a job_id for async jobs

#call the zip_handler.py with method:
#extract and save zip file

# call the skill_validator.py

#return job id to client

#clean up temp

# POST /upload

# save_and_extract(file, job_id)
# result = validate(job_id)
# enqueue(job_id)
# return {job_id, status}

from pathlib import Path
import shutil

from fastapi import APIRouter, File, Header, HTTPException, UploadFile
from pydantic import BaseModel, Field

from backend.config import settings
from backend.services.validator.main_validator import run_validator
from schemas.models.payload_schemas import UploadSkillRequest

router = APIRouter(tags=["upload"])

@router.post("/upload")
def upload_skill(payload: UploadSkillRequest) -> dict:
    validator_response = run_validator(payload.file)

    return {"status": validator_response.status, "job_id": validator_response.job_id}