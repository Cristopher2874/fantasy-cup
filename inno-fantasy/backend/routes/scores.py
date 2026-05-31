"""Scoring result endpoints."""
from __future__ import annotations

import secrets
from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, Query

from config.config_provider import GlobalConfigProvider
from services.score_engine import get_leaderboard, get_score_result, list_score_results, score_existing_job


CONFIG = GlobalConfigProvider()
SCORE_WRITE_REQUIRES_TOKEN = CONFIG.get_bool("admin_routes", "score_write_requires_token", True)
SCORE_WRITE_HEADER = CONFIG.get_str("admin_routes", "score_write_header", "x-admin-token")
SCORE_WRITE_TOKEN = CONFIG.get_str("admin_routes", "score_write_token", "")

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
def score_job(
    job_id: str,
    force: bool = Query(default=False),
    admin_token: Annotated[str | None, Header(alias=SCORE_WRITE_HEADER)] = None,
) -> dict:
    _authorize_score_write(admin_token)
    result = score_existing_job(job_id, force=force)
    if not result.success:
        raise HTTPException(status_code=400, detail=result.issues)
    return result.to_dict()


def _authorize_score_write(admin_token: str | None) -> None:
    if not SCORE_WRITE_REQUIRES_TOKEN:
        return
    if not SCORE_WRITE_TOKEN:
        raise HTTPException(
            status_code=503,
            detail="Manual scoring is protected but INNO_FANTASY_ADMIN_TOKEN is not configured.",
        )
    if not admin_token or not secrets.compare_digest(admin_token, SCORE_WRITE_TOKEN):
        raise HTTPException(status_code=403, detail="Admin token is required for manual scoring.")
