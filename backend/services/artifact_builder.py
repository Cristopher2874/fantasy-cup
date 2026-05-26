from pathlib import Path
import shutil

from backend.config import settings
from backend.services.leaderboard import rebuild_leaderboard
from backend.services.state_store import utc_now


def build_artifacts(store, matchday_id: str) -> str:
    matchday = store.find_by_id("matchdays", matchday_id)
    if not matchday:
        raise ValueError(f"Unknown matchday: {matchday_id}")

    target = settings.artifacts_dir / matchday_id / "tournament"
    data_dir = target / "data"
    schema_dir = target / "answer-formats"
    data_dir.mkdir(parents=True, exist_ok=True)
    schema_dir.mkdir(parents=True, exist_ok=True)

    (target / "rules.md").write_text(build_rules_markdown(), encoding="utf-8")
    for schema_path in settings.schemas_dir.glob("*.schema.json"):
        shutil.copyfile(schema_path, schema_dir / schema_path.name)

    store.write_json(data_dir / "matchday.json", public_matchday(matchday))
    store.write_json(data_dir / "teams.json", public_teams(store.read("teams")))
    store.write_json(data_dir / "players.json", public_players(matchday))
    store.write_json(data_dir / "matches.json", public_matches(matchday))
    store.write_json(data_dir / "risk-claims.json", public_risk_claims(matchday))
    store.write_json(data_dir / "standings.json", rebuild_leaderboard(store))

    matchday["artifact_path"] = str(target.relative_to(settings.project_root))
    matchday["artifact_built_at"] = utc_now()
    if matchday.get("status") == "draft":
        matchday["status"] = "artifacts_built"
    store.update("matchdays", matchday_id, matchday)
    return matchday["artifact_path"]


def public_matchday(matchday: dict) -> dict:
    return {
        "id": matchday["id"],
        "label": matchday.get("label", matchday["id"]),
        "match_date": matchday.get("match_date"),
        "stage": matchday.get("stage", "league"),
        "status": matchday.get("status", "draft"),
        "artifact_path": matchday.get("artifact_path"),
        "matches": public_matches(matchday),
        "player_count": len(matchday.get("players", [])),
        "risk_claim_count": len(matchday.get("risk_claims", [])),
        "created_at": matchday.get("created_at"),
        "published_at": matchday.get("published_at"),
    }


def public_players(matchday: dict) -> list[dict]:
    return [
        {
            "id": player["id"],
            "name": player["name"],
            "team_id": player["team_id"],
            "team": player["team"],
            "position": player["position"],
            "match_id": player["match_id"],
            "eligible": player.get("eligible", True),
        }
        for player in matchday.get("players", [])
    ]


def public_matches(matchday: dict) -> list[dict]:
    return [
        {
            "id": match["id"],
            "home_team_id": match["home_team_id"],
            "home_team": match["home_team"],
            "away_team_id": match["away_team_id"],
            "away_team": match["away_team"],
            "kickoff": match["kickoff"],
            "public": match.get("public", True),
        }
        for match in matchday.get("matches", [])
    ]


def public_risk_claims(matchday: dict) -> list[dict]:
    claims = []
    for claim in matchday.get("risk_claims", []):
        visible = {key: value for key, value in claim.items() if key != "outcome"}
        claims.append(visible)
    return claims


def public_teams(teams: list[dict]) -> list[dict]:
    return [
        {
            "id": team["id"],
            "name": team["name"],
            "members": team.get("members", []),
            "submission_method": team.get("submission_method"),
            "created_at": team.get("created_at"),
        }
        for team in teams
    ]


def build_rules_markdown() -> str:
    return """# AI Agent Fantasy World Cup Rules

Pick exactly eleven eligible players from the official matchday files.

Position requirements:

- GK: exactly 1
- DEF: 3 to 5
- MID: 3 to 5
- FWD: 1 to 3

Risk Play is optional. Select one published claim or return null.

The answer file must include `fantasy_xi`, `risk_play`, and `strategy_summary`.
"""
