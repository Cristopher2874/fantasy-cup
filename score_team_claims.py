from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


TRUTH_PATH = Path("truth_data/latest_truth.json")
SUBMISSIONS_PATH = Path("mock_team_claims_2022.json")
LEADERBOARD_PATH = Path("mock_leaderboard_2022.json")
OUTPUT_DIR = Path("score_data")

MATCHDAY_RESULTS_PATH = OUTPUT_DIR / "matchday_results.json"
UPDATED_LEADERBOARD_PATH = OUTPUT_DIR / "leaderboard.json"

POSITION_RULES = {
    "GK": (1, 1),
    "DEF": (3, 5),
    "MID": (3, 5),
    "FWD": (1, 3),
}

CATEGORY_STAKES = {
    "green": 0.15,
    "yellow": 0.25,
    "red": 0.35,
}


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict | list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_context(truth: dict) -> dict:
    players = truth.get("players", [])
    matches = truth.get("matches", [])
    player_by_record_id = {player["record_id"]: player for player in players}
    records_by_player_id: dict[str, list[dict]] = {}
    for player in players:
        records_by_player_id.setdefault(str(player["id"]), []).append(player)

    return {
        "truth": truth,
        "match_by_id": {str(match["id"]): match for match in matches},
        "player_by_record_id": player_by_record_id,
        "records_by_player_id": records_by_player_id,
        "risk_capabilities": truth.get("capabilities", {}).get("risk_claims", {}),
    }


def resolve_player_selection(selection: Any, context: dict) -> tuple[dict | None, str | None]:
    if isinstance(selection, str):
        if ":" in selection:
            player = context["player_by_record_id"].get(selection)
            return player, None if player else f"Unknown player record_id: {selection}"

        records = context["records_by_player_id"].get(selection, [])
        if len(records) == 1:
            return records[0], None
        if not records:
            return None, f"Unknown player_id: {selection}"
        return None, f"Ambiguous bare player_id {selection}; use record_id or match_id/player_id"

    if isinstance(selection, dict):
        record_id = selection.get("record_id")
        if record_id:
            player = context["player_by_record_id"].get(record_id)
            return player, None if player else f"Unknown player record_id: {record_id}"

        match_id = selection.get("match_id")
        player_id = selection.get("player_id")
        if match_id and player_id:
            lookup_key = f"{match_id}:{player_id}"
            player = context["player_by_record_id"].get(lookup_key)
            return player, None if player else f"Unknown match_id/player_id pair: {lookup_key}"

    return None, f"Invalid player selection format: {selection!r}"


def validate_and_score_fantasy_xi(fantasy_xi: Any, context: dict) -> dict:
    errors = []
    warnings = []
    resolved_players = []

    if not isinstance(fantasy_xi, list):
        return {
            "valid": False,
            "points": 0,
            "errors": ["fantasy_xi must be a list"],
            "warnings": [],
            "players": [],
            "position_counts": {},
        }

    if len(fantasy_xi) != 11:
        errors.append(f"fantasy_xi must contain exactly 11 selections; received {len(fantasy_xi)}")

    seen_record_ids = set()
    for selection in fantasy_xi:
        player, error = resolve_player_selection(selection, context)
        if error:
            errors.append(error)
            continue
        if player["record_id"] in seen_record_ids:
            errors.append(f"Duplicate player record_id: {player['record_id']}")
            continue
        seen_record_ids.add(player["record_id"])
        resolved_players.append(player)

    position_counts = {position: 0 for position in POSITION_RULES}
    for player in resolved_players:
        position = player.get("position")
        if position in position_counts:
            position_counts[position] += 1
        else:
            errors.append(f"Unsupported position for {player['record_id']}: {position}")

    for position, (minimum, maximum) in POSITION_RULES.items():
        count = position_counts[position]
        if count < minimum or count > maximum:
            errors.append(f"{position} count must be between {minimum} and {maximum}; received {count}")

    if errors:
        return {
            "valid": False,
            "points": 0,
            "errors": errors,
            "warnings": warnings,
            "players": summarize_players(resolved_players),
            "position_counts": position_counts,
        }

    points = sum(int(player.get("fantasy_points", 0)) for player in resolved_players)
    return {
        "valid": True,
        "points": points,
        "errors": [],
        "warnings": warnings,
        "players": summarize_players(resolved_players),
        "position_counts": position_counts,
    }


def summarize_players(players: list[dict]) -> list[dict]:
    return [
        {
            "record_id": player["record_id"],
            "match_id": player["match_id"],
            "player_id": player["id"],
            "name": player["name"],
            "team": player["team"],
            "position": player["position"],
            "points": player.get("fantasy_points", 0),
            "breakdown": player.get("fantasy_breakdown", []),
        }
        for player in players
    ]


def validate_required_fields(risk_play: dict, required_fields: list[str]) -> list[str]:
    missing = []
    for field in required_fields:
        if field not in risk_play or risk_play.get(field) in {None, ""}:
            missing.append(field)
    return missing


def resolve_risk_outcome(risk_play: dict, match: dict) -> tuple[bool | None, str]:
    claim_id = risk_play["claim_id"]
    risk_truth = match.get("risk_truth", {})
    match_claims = risk_truth.get("match_claims", {})
    parameterized_claims = risk_truth.get("parameterized_claims", {})

    if claim_id in match_claims:
        return bool(match_claims[claim_id]), f"match_claims.{claim_id}"

    if claim_id == "exact_score":
        expected = parameterized_claims.get("exact_score", {})
        actual_home = int(risk_play.get("home_score", -999999))
        actual_away = int(risk_play.get("away_score", -999999))
        return (
            actual_home == int(expected.get("home_score", -1))
            and actual_away == int(expected.get("away_score", -1)),
            "parameterized_claims.exact_score",
        )

    if claim_id in {"team_scores_first", "team_wins_by_3plus", "team_comeback_win"}:
        team_id = str(risk_play.get("team_id"))
        values = parameterized_claims.get(claim_id, {})
        return bool(values.get(team_id, False)), f"parameterized_claims.{claim_id}.{team_id}"

    if claim_id in {"player_scores", "player_scores_2plus"}:
        player_id = str(risk_play.get("player_id"))
        values = parameterized_claims.get(claim_id, {})
        return bool(values.get(player_id, False)), f"parameterized_claims.{claim_id}.{player_id}"

    return None, f"Unsupported risk claim resolver: {claim_id}"


def validate_and_score_risk_play(risk_play: Any, previous_total: float, context: dict) -> dict:
    if risk_play is None:
        return {
            "valid": True,
            "outcome": "skipped",
            "points": 0,
            "stake": 0,
            "errors": [],
            "warnings": [],
            "claim_id": None,
        }

    if not isinstance(risk_play, dict):
        return {
            "valid": False,
            "outcome": "invalid",
            "points": 0,
            "stake": 0,
            "errors": ["risk_play must be an object or null"],
            "warnings": [],
            "claim_id": None,
        }

    errors = []
    warnings = []
    claim_id = risk_play.get("claim_id")
    match_id = str(risk_play.get("match_id", ""))
    capability = context["risk_capabilities"].get(claim_id)
    match = context["match_by_id"].get(match_id)

    if not claim_id:
        errors.append("risk_play.claim_id is required")
    if not capability:
        errors.append(f"Unsupported risk_play.claim_id: {claim_id}")
    if not match_id:
        errors.append("risk_play.match_id is required")
    elif not match:
        errors.append(f"Unknown risk_play.match_id: {match_id}")

    if capability:
        missing = validate_required_fields(risk_play, capability.get("required_fields", []))
        if missing:
            errors.append(f"risk_play missing required fields: {', '.join(missing)}")

        submitted_category = risk_play.get("category")
        canonical_category = capability.get("category")
        if submitted_category and str(submitted_category).lower() != canonical_category:
            warnings.append(
                f"Submitted category {submitted_category!r} ignored; canonical category is {canonical_category!r}"
            )

    if errors:
        return {
            "valid": False,
            "outcome": "invalid",
            "points": 0,
            "stake": 0,
            "errors": errors,
            "warnings": warnings,
            "claim_id": claim_id,
        }

    correct, evidence_path = resolve_risk_outcome(risk_play, match)
    if correct is None:
        return {
            "valid": False,
            "outcome": "invalid",
            "points": 0,
            "stake": 0,
            "errors": [evidence_path],
            "warnings": warnings,
            "claim_id": claim_id,
        }

    category = capability["category"]
    stake = round(previous_total * CATEGORY_STAKES[category], 2)
    points = stake if correct else -stake
    return {
        "valid": True,
        "outcome": "correct" if correct else "incorrect",
        "correct": correct,
        "points": points,
        "stake": stake,
        "category": category,
        "claim_id": claim_id,
        "match_id": match_id,
        "evidence_path": evidence_path,
        "errors": [],
        "warnings": warnings,
    }


def score_submission(submission: dict, leaderboard_entry: dict, context: dict) -> dict:
    answers = submission.get("answers", {})
    previous_total = float(leaderboard_entry.get("total_points", 0))
    fantasy = validate_and_score_fantasy_xi(answers.get("fantasy_xi"), context)
    risk = validate_and_score_risk_play(answers.get("risk_play"), previous_total, context)
    fantasy_points = fantasy["points"] if fantasy["valid"] else 0
    risk_points = risk["points"] if risk["valid"] else 0
    total_delta = round(fantasy_points + risk_points, 2)

    return {
        "team_id": submission["team_id"],
        "team_name": submission.get("team_name", leaderboard_entry.get("team_name", submission["team_id"])),
        "previous_total_points": previous_total,
        "fantasy": fantasy,
        "risk": risk,
        "strategy_summary": answers.get("strategy_summary", ""),
        "fantasy_points": fantasy_points,
        "risk_points": risk_points,
        "total_delta": total_delta,
        "new_total_points": round(previous_total + total_delta, 2),
        "status": "scored" if fantasy["valid"] and risk["valid"] else "scored_with_errors",
    }


def leaderboard_lookup(leaderboard: dict) -> dict[str, dict]:
    return {entry["team_id"]: entry for entry in leaderboard.get("teams", [])}


def update_leaderboard(leaderboard: dict, results: list[dict]) -> dict:
    existing = leaderboard_lookup(leaderboard)
    updated = {}

    for team_id, entry in existing.items():
        updated[team_id] = dict(entry)

    for result in results:
        team_id = result["team_id"]
        entry = updated.setdefault(
            team_id,
            {
                "team_id": team_id,
                "team_name": result["team_name"],
                "total_points": 0,
                "fantasy_points": 0,
                "risk_points": 0,
                "matchdays_played": 0,
            },
        )
        entry["team_name"] = result["team_name"]
        entry["total_points"] = result["new_total_points"]
        entry["fantasy_points"] = round(float(entry.get("fantasy_points", 0)) + result["fantasy_points"], 2)
        entry["risk_points"] = round(float(entry.get("risk_points", 0)) + result["risk_points"], 2)
        entry["matchdays_played"] = int(entry.get("matchdays_played", 0)) + 1
        entry["last_status"] = result["status"]

    teams = sorted(updated.values(), key=lambda item: (-float(item.get("total_points", 0)), item["team_name"]))
    for index, entry in enumerate(teams, start=1):
        entry["rank"] = index

    return {
        "schema_version": "fantasy-cup-leaderboard-v1",
        "updated_at": utc_now(),
        "teams": teams,
    }


def run_scoring() -> tuple[Path, Path]:
    truth = load_json(TRUTH_PATH)
    submissions = load_json(SUBMISSIONS_PATH)
    leaderboard = load_json(LEADERBOARD_PATH)
    context = build_context(truth)
    entries = leaderboard_lookup(leaderboard)

    results = []
    for submission in submissions.get("submissions", []):
        team_id = submission["team_id"]
        leaderboard_entry = entries.get(
            team_id,
            {
                "team_id": team_id,
                "team_name": submission.get("team_name", team_id),
                "total_points": 0,
                "fantasy_points": 0,
                "risk_points": 0,
                "matchdays_played": 0,
            },
        )
        results.append(score_submission(submission, leaderboard_entry, context))

    matchday_results = {
        "schema_version": "fantasy-cup-matchday-results-v1",
        "generated_at": utc_now(),
        "truth_path": str(TRUTH_PATH),
        "submissions_path": str(SUBMISSIONS_PATH),
        "leaderboard_input_path": str(LEADERBOARD_PATH),
        "matchday_id": submissions.get("matchday_id", truth.get("matchday_id")),
        "results": results,
    }
    updated_leaderboard = update_leaderboard(leaderboard, results)

    write_json(MATCHDAY_RESULTS_PATH, matchday_results)
    write_json(UPDATED_LEADERBOARD_PATH, updated_leaderboard)
    return MATCHDAY_RESULTS_PATH, UPDATED_LEADERBOARD_PATH


def main() -> int:
    try:
        results_path, leaderboard_path = run_scoring()
    except Exception as error:
        print(f"Team scoring failed: {error}", file=sys.stderr)
        return 1

    print(f"Matchday results: {results_path}")
    print(f"Updated leaderboard: {leaderboard_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
