from pathlib import Path
import json

from backend.runners.base import AgentRunner


class MockAgentRunner(AgentRunner):
    def run(self, team: dict, snapshot: dict, matchday: dict, artifact_path: str, run_dir: Path) -> dict:
        selected_ids = pick_fantasy_xi(matchday.get("players", []), team["id"])
        risk_play = pick_risk_claim(matchday.get("risk_claims", []), team["id"])
        answers = {
            "fantasy_xi": selected_ids,
            "risk_play": risk_play,
            "strategy_summary": (
                f"{team['name']} leaned on likely starters, balanced position counts, "
                "and used the mock ranking signal to keep the XI valid for the local POC."
            ),
        }

        raw_response = {
            "runner": "mock",
            "snapshot_id": snapshot["id"],
            "artifact_path": artifact_path,
            "message": "Deterministic local runner generated phase 1 answers.",
        }
        write_json(run_dir / "answers.json", answers)
        write_json(run_dir / "raw_response.json", raw_response)
        (run_dir / "strategy_summary.txt").write_text(answers["strategy_summary"], encoding="utf-8")
        (run_dir / "logs.txt").write_text(
            "MockAgentRunner loaded official artifacts and produced answers.json.\n",
            encoding="utf-8",
        )
        return {"answers": answers, "raw_response": raw_response}


def pick_fantasy_xi(players: list[dict], team_id: str) -> list[str]:
    eligible = [player for player in players if player.get("eligible", True)]
    offset = sum(ord(char) for char in team_id) % 2
    target_counts = {"GK": 1, "DEF": 4, "MID": 4, "FWD": 2}
    selected: list[dict] = []
    for position, count in target_counts.items():
        position_players = [player for player in eligible if player["position"] == position]
        position_players.sort(key=lambda player: player.get("mock_rank", 0), reverse=True)
        if offset and len(position_players) > count:
            position_players = position_players[1:] + position_players[:1]
        selected.extend(position_players[:count])
    return [player["id"] for player in selected]


def pick_risk_claim(claims: list[dict], team_id: str) -> dict | None:
    if not claims:
        return None
    index = sum(ord(char) for char in team_id) % len(claims)
    claim = claims[index]
    risk_play = {"claim_id": claim["id"]}
    for field in claim.get("required_fields", []):
        if field in claim:
            risk_play[field] = claim[field]
    return risk_play


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
