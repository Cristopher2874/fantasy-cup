from fastapi import APIRouter, HTTPException

from backend.config import settings
from backend.services.artifact_builder import public_matchday
from backend.services.leaderboard import rebuild_leaderboard
from backend.services.state_store import store

router = APIRouter(tags=["public"])


@router.get("/leaderboard")
def get_leaderboard() -> list[dict]:
    return rebuild_leaderboard(store)


@router.get("/matchdays")
def get_matchdays() -> list[dict]:
    matchdays = store.read("matchdays")
    return [public_matchday(matchday) for matchday in matchdays]


@router.get("/matchdays/{matchday_id}/results")
def get_matchday_results(matchday_id: str) -> dict:
    matchday = store.find_by_id("matchdays", matchday_id)
    if not matchday:
        raise HTTPException(status_code=404, detail="Matchday not found")

    runs = [
        public_run(run)
        for run in store.read("runs")
        if run["matchday_id"] == matchday_id
    ]
    runs.sort(key=lambda run: run["created_at"], reverse=True)
    latest_by_team = {}
    for run in runs:
        latest_by_team.setdefault(run["team_id"], run)

    return {
        "matchday": public_matchday(matchday),
        "runs": list(latest_by_team.values()),
    }


@router.get("/catalog")
def get_catalog() -> dict:
    schemas = {}
    for schema_path in sorted(settings.schemas_dir.glob("*.schema.json")):
        schemas[schema_path.name] = schema_path.read_text(encoding="utf-8")

    return {
        "entities": [
            {
                "name": "Players",
                "fields": [
                    {"name": "id", "type": "string", "description": "Official player ID used in answers."},
                    {"name": "name", "type": "string", "description": "Player display name."},
                    {"name": "team_id", "type": "string", "description": "National team ID."},
                    {"name": "position", "type": "GK | DEF | MID | FWD", "description": "Fantasy roster position."},
                    {"name": "eligible", "type": "boolean", "description": "Whether the player can be selected for the matchday."},
                ],
            },
            {
                "name": "Risk claims",
                "fields": [
                    {"name": "claim_id", "type": "string", "description": "Official claim ID."},
                    {"name": "category", "type": "green | yellow | red", "description": "Stake category."},
                    {"name": "required_fields", "type": "string[]", "description": "Fields the agent must echo when selecting the claim."},
                ],
            },
            {
                "name": "Fantasy XI answer",
                "fields": [
                    {"name": "fantasy_xi", "type": "string[11]", "description": "Exactly eleven unique eligible player IDs."},
                    {"name": "risk_play", "type": "object | null", "description": "One selected published risk claim, or null."},
                    {"name": "strategy_summary", "type": "string", "description": "Short explanation for the selected approach."},
                ],
            },
        ],
        "position_rules": {
            "GK": "exactly 1",
            "DEF": "3 to 5",
            "MID": "3 to 5",
            "FWD": "1 to 3",
            "total": "exactly 11",
        },
        "scoring": {
            "starts": 2,
            "plays_60_minutes": 2,
            "goal": 6,
            "assist": 4,
            "clean_sheet_def_gk": 4,
            "goalkeeper_3_saves": 2,
            "yellow_card": -1,
            "red_card": -3,
            "own_goal": -3,
        },
        "schemas": schemas,
    }


def public_run(run: dict) -> dict:
    return {
        "id": run["id"],
        "team_id": run["team_id"],
        "team_name": run.get("team_name"),
        "matchday_id": run["matchday_id"],
        "status": run["status"],
        "runner": run["runner"],
        "answers": run.get("answers", {}),
        "validation": run.get("validation", {}),
        "scoring": run.get("scoring", {}),
        "fantasy_points": run.get("fantasy_points", 0),
        "risk_points": run.get("risk_points", 0),
        "bracket_points": run.get("bracket_points", 0),
        "total_points": run.get("total_points", 0),
        "strategy_summary": run.get("strategy_summary", ""),
        "created_at": run["created_at"],
    }
