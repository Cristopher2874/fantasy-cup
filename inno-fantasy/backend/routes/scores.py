"""Scoring result endpoints."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from services.score_engine import get_leaderboard, get_score_result, list_score_results, score_existing_job


router = APIRouter(prefix="/scores", tags=["scores"])


@router.get("")
def list_scores() -> dict:
    return {
        "leaderboard": get_leaderboard(),
        "scores": list_score_results(),
    }


@router.get("/{job_id}")
def read_score(job_id: str) -> dict:
    score = get_score_result(job_id)
    if score is None:
        raise HTTPException(status_code=404, detail=f"Score result not found for job id: {job_id}")
    return score


@router.post("/{job_id}/score")
def score_job(job_id: str, force: bool = Query(default=False)) -> dict:
    result = score_existing_job(job_id, force=force)
    if not result.success:
        raise HTTPException(status_code=400, detail=result.issues)
    return result.to_dict()
