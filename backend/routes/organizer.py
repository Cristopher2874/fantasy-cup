from pydantic import BaseModel
from fastapi import APIRouter, HTTPException

from backend.config import settings
from backend.runners.mock_runner import MockAgentRunner
from backend.services.answer_validator import validate_answers
from backend.services.artifact_builder import build_artifacts
from backend.services.leaderboard import rebuild_leaderboard, team_points_before_matchday
from backend.services.risk_resolver import resolve_risk_play
from backend.services.sample_data import build_mock_matchday, seed_demo
from backend.services.scorer import score_fantasy_xi
from backend.services.state_store import store, utc_now

router = APIRouter(tags=["organizer"])


class MatchdayRequest(BaseModel):
    id: str | None = None
    label: str | None = None
    match_date: str | None = None
    stage: str = "league"


@router.post("/org/demo/seed")
def seed_demo_data() -> dict:
    result = seed_demo(store)
    result["leaderboard"] = rebuild_leaderboard(store)
    return result


@router.post("/org/matchdays")
def create_matchday(payload: MatchdayRequest) -> dict:
    matchday_id = payload.id or store.next_id("MD", "matchdays")
    if store.find_by_id("matchdays", matchday_id):
        raise HTTPException(status_code=409, detail="Matchday already exists")

    matchday = build_mock_matchday(
        matchday_id=matchday_id,
        label=payload.label or f"Mock Matchday {matchday_id[-3:]}",
        match_date=payload.match_date,
        stage=payload.stage,
    )
    store.append("matchdays", matchday)
    return {"matchday": matchday}


@router.post("/org/matchdays/{matchday_id}/build-artifacts")
def build_matchday_artifacts(matchday_id: str) -> dict:
    matchday = store.find_by_id("matchdays", matchday_id)
    if not matchday:
        raise HTTPException(status_code=404, detail="Matchday not found")
    artifact_path = build_artifacts(store, matchday_id)
    return {"matchday_id": matchday_id, "artifact_path": artifact_path}


@router.post("/org/matchdays/{matchday_id}/run")
def run_matchday(matchday_id: str) -> dict:
    matchday = store.find_by_id("matchdays", matchday_id)
    if not matchday:
        raise HTTPException(status_code=404, detail="Matchday not found")

    artifact_path = build_artifacts(store, matchday_id)
    runner = MockAgentRunner()
    created_runs = []

    for team in store.read("teams"):
        snapshot = latest_snapshot(team["id"])
        if not snapshot:
            continue

        run_id = store.next_id("RUN", "runs")
        run_dir = settings.runs_dir / matchday_id / team["id"] / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        runner_result = runner.run(team, snapshot, matchday, artifact_path, run_dir)
        answers = runner_result["answers"]
        validation = validate_answers(answers, matchday)

        fantasy_scoring = {"total": 0, "players": [], "errors": validation["sections"]["fantasy_xi"]["errors"]}
        if validation["sections"]["fantasy_xi"]["valid"]:
            fantasy_scoring = score_fantasy_xi(answers["fantasy_xi"], matchday)

        risk_scoring = {"outcome": "skipped", "points": 0, "stake": 0}
        if validation["sections"]["risk_play"]["valid"]:
            prior_points = team_points_before_matchday(store, team["id"], matchday_id)
            risk_scoring = resolve_risk_play(answers.get("risk_play"), matchday, prior_points)

        scoring = {
            "fantasy": fantasy_scoring,
            "risk": risk_scoring,
            "bracket": {"points": 0, "status": "not_in_phase_1"},
        }
        total_points = fantasy_scoring["total"] + risk_scoring["points"]
        status = "scored" if validation["sections"]["fantasy_xi"]["valid"] else "scored_with_errors"

        run = {
            "id": run_id,
            "team_id": team["id"],
            "team_name": team["name"],
            "matchday_id": matchday_id,
            "snapshot_id": snapshot["id"],
            "status": status,
            "runner": "mock",
            "answers": answers,
            "validation": validation,
            "scoring": scoring,
            "fantasy_points": fantasy_scoring["total"],
            "risk_points": risk_scoring["points"],
            "bracket_points": 0,
            "total_points": total_points,
            "risk_outcome": risk_scoring["outcome"],
            "strategy_summary": answers.get("strategy_summary", ""),
            "artifact_path": str(run_dir.relative_to(settings.project_root)),
            "created_at": utc_now(),
        }
        store.write_json(run_dir / "validation.json", validation)
        store.write_json(run_dir / "scoring.json", scoring)
        store.append("runs", run)
        created_runs.append(run)

    leaderboard = rebuild_leaderboard(store)
    matchday["status"] = "scored"
    matchday["artifact_path"] = artifact_path
    matchday["updated_at"] = utc_now()
    store.update("matchdays", matchday_id, matchday)

    return {"matchday_id": matchday_id, "runs": created_runs, "leaderboard": leaderboard}


@router.post("/org/matchdays/{matchday_id}/score")
def score_matchday(matchday_id: str) -> dict:
    matchday = store.find_by_id("matchdays", matchday_id)
    if not matchday:
        raise HTTPException(status_code=404, detail="Matchday not found")
    leaderboard = rebuild_leaderboard(store)
    return {"matchday_id": matchday_id, "leaderboard": leaderboard}


@router.post("/org/matchdays/{matchday_id}/publish")
def publish_matchday(matchday_id: str) -> dict:
    matchday = store.find_by_id("matchdays", matchday_id)
    if not matchday:
        raise HTTPException(status_code=404, detail="Matchday not found")
    matchday["status"] = "published"
    matchday["published_at"] = utc_now()
    store.update("matchdays", matchday_id, matchday)
    leaderboard = rebuild_leaderboard(store)
    return {"matchday": matchday, "leaderboard": leaderboard}


@router.get("/org/runs/{run_id}/logs")
def get_run_logs(run_id: str) -> dict:
    run = store.find_by_id("runs", run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    logs_path = settings.project_root / run["artifact_path"] / "logs.txt"
    logs = logs_path.read_text(encoding="utf-8") if logs_path.exists() else ""
    return {"run_id": run_id, "logs": logs}


def latest_snapshot(team_id: str) -> dict | None:
    snapshots = [
        item
        for item in store.read("snapshots")
        if item["team_id"] == team_id and item.get("accepted")
    ]
    snapshots.sort(key=lambda item: item["created_at"], reverse=True)
    return snapshots[0] if snapshots else None
