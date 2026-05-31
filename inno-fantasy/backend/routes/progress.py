"""Progress endpoints for validation-triggered Codex executions."""
from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from services.pipeline import get_pipeline_job, list_pipeline_jobs


router = APIRouter(tags=["progress"])


@router.get("/progress")
def list_progress() -> dict:
    return {"jobs": list_pipeline_jobs()}


@router.get("/progress/{job_id}")
def read_progress(job_id: str) -> dict:
    job = get_pipeline_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Pipeline job not found: {job_id}")
    return job


@router.get("/progress/{job_id}/stream")
async def stream_progress(job_id: str) -> StreamingResponse:
    async def events():
        last_payload = None
        while True:
            job = get_pipeline_job(job_id)
            if job is None:
                yield _sse({"status": "missing", "message": f"Pipeline job not found: {job_id}"})
                return

            payload = json.dumps(job, sort_keys=True)
            if payload != last_payload:
                yield f"event: progress\ndata: {payload}\n\n"
                last_payload = payload

            if job["status"] in {"completed", "failed"}:
                return
            await asyncio.sleep(1)

    return StreamingResponse(events(), media_type="text/event-stream")


def _sse(payload: dict) -> str:
    return f"event: progress\ndata: {json.dumps(payload, sort_keys=True)}\n\n"
