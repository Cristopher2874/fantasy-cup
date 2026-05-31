"""Score Codex team submissions against generated source-of-truth data."""
from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from config.config_provider import GlobalConfigProvider
from services.data_generator.source_of_truth import DEFAULT_TRUTH_DIR, create_source_truth_snapshot


BACKEND_ROOT = Path(__file__).resolve().parent.parent
INNO_ROOT = BACKEND_ROOT.parent
RUNS_ROOT = INNO_ROOT / "data" / "runs"
SCORES_ROOT = INNO_ROOT / "data" / "scores"
LEADERBOARD_PATH = SCORES_ROOT / "leaderboard.json"
SCORED_JOBS_DIR = SCORES_ROOT / "jobs"
INITIAL_TEAM_POINTS = GlobalConfigProvider().get_float("scoring", "initial_team_points", 0.0)

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


@dataclass
class ScoreRunResult:
    success: bool
    result_path: Path | None = None
    leaderboard_path: Path | None = None
    truth_path: Path | None = None
    issues: list[str] = field(default_factory=list)
    result: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "result_path": str(self.result_path) if self.result_path else None,
            "leaderboard_path": str(self.leaderboard_path) if self.leaderboard_path else None,
            "truth_path": str(self.truth_path) if self.truth_path else None,
            "issues": self.issues,
            "result": self.result,
        }


class TeamClaimsScorer:
    def __init__(self, truth: dict[str, Any]) -> None:
        self.truth = truth
        self.match_by_id = {str(match["id"]): match for match in truth.get("matches", [])}
        self.player_by_record_id = {player["record_id"]: player for player in truth.get("players", [])}
        self.records_by_player_id: dict[str, list[dict[str, Any]]] = {}
        for player in truth.get("players", []):
            self.records_by_player_id.setdefault(str(player["id"]), []).append(player)
        self.risk_capabilities = truth.get("capabilities", {}).get("risk_claims", {})

    def score_submission(self, submission: dict[str, Any], leaderboard_entry: dict[str, Any]) -> dict[str, Any]:
        answers = submission.get("answers", {})
        previous_total = float(leaderboard_entry.get("total_points", INITIAL_TEAM_POINTS))
        fantasy = self.validate_and_score_fantasy_xi(answers.get("fantasy_xi"))
        risk = self.validate_and_score_risk_play(answers.get("risk_play"), previous_total)
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

    def validate_and_score_fantasy_xi(self, fantasy_xi: Any) -> dict[str, Any]:
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
            player, error = self.resolve_player_selection(selection)
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
                "players": self.summarize_players(resolved_players),
                "position_counts": position_counts,
            }

        points = sum(int(player.get("fantasy_points", 0)) for player in resolved_players)
        return {
            "valid": True,
            "points": points,
            "errors": [],
            "warnings": warnings,
            "players": self.summarize_players(resolved_players),
            "position_counts": position_counts,
        }

    def validate_and_score_risk_play(self, risk_play: Any, previous_total: float) -> dict[str, Any]:
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
        capability = self.risk_capabilities.get(claim_id)
        match = self.match_by_id.get(match_id)

        if not claim_id:
            errors.append("risk_play.claim_id is required")
        if not capability:
            errors.append(f"Unsupported risk_play.claim_id: {claim_id}")
        if not match_id:
            errors.append("risk_play.match_id is required")
        elif not match:
            errors.append(f"Unknown risk_play.match_id: {match_id}")

        if capability:
            missing = self.validate_required_fields(risk_play, capability.get("required_fields", []))
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

        correct, evidence_path = self.resolve_risk_outcome(risk_play, match)
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
        #TODO: check for 0 point teams and those that might have negatives can sum
        if previous_total == 0:
            previous_total = 1
        stake = round(abs(previous_total) * CATEGORY_STAKES[category], 2)
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

    def resolve_player_selection(self, selection: Any) -> tuple[dict[str, Any] | None, str | None]:
        if isinstance(selection, str):
            return self._resolve_record_or_player_id(selection)

        if isinstance(selection, dict):
            record_id = selection.get("record_id")
            if record_id:
                player = self.player_by_record_id.get(record_id)
                return player, None if player else f"Unknown player record_id: {record_id}"

            match_id = selection.get("match_id")
            player_id = selection.get("player_id")
            if match_id and player_id:
                lookup_key = f"{match_id}:{player_id}"
                player = self.player_by_record_id.get(lookup_key)
                return player, None if player else f"Unknown match_id/player_id pair: {lookup_key}"

        return None, f"Invalid player selection format: {selection!r}"

    def _resolve_record_or_player_id(self, value: str) -> tuple[dict[str, Any] | None, str | None]:
        if ":" in value:
            player = self.player_by_record_id.get(value)
            return player, None if player else f"Unknown player record_id: {value}"

        records = self.records_by_player_id.get(value, [])
        if len(records) == 1:
            return records[0], None
        if not records:
            return None, f"Unknown player_id: {value}"
        return None, f"Ambiguous bare player_id {value}; use record_id or match_id/player_id"

    def resolve_risk_outcome(self, risk_play: dict[str, Any], match: dict[str, Any]) -> tuple[bool | None, str]:
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

        if claim_id in {"team_scores_first", "team_wins_by_3plus"}:
            team_id = str(risk_play.get("team_id"))
            values = parameterized_claims.get(claim_id, {})
            return bool(values.get(team_id, False)), f"parameterized_claims.{claim_id}.{team_id}"

        if claim_id in {"player_scores", "player_scores_2plus"}:
            player_id = str(risk_play.get("player_id"))
            values = parameterized_claims.get(claim_id, {})
            return bool(values.get(player_id, False)), f"parameterized_claims.{claim_id}.{player_id}"

        return None, f"Unsupported risk claim resolver: {claim_id}"

    @staticmethod
    def summarize_players(players: list[dict[str, Any]]) -> list[dict[str, Any]]:
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

    @staticmethod
    def validate_required_fields(risk_play: dict[str, Any], required_fields: list[str]) -> list[str]:
        return [field for field in required_fields if field not in risk_play or risk_play.get(field) in {None, ""}]


def score_codex_submission(
    *,
    job_id: str,
    submission_path: Path,
    run_dir: Path,
    force: bool = False,
) -> ScoreRunResult:
    """Score one Codex submission and persist result files for the API."""
    result_path = run_dir / "score_result.json"
    central_result_path = SCORED_JOBS_DIR / f"{job_id}.score.json"
    if result_path.is_file() and central_result_path.is_file() and not force:
        result = _load_json(result_path)
        return ScoreRunResult(
            success=True,
            result_path=result_path,
            leaderboard_path=LEADERBOARD_PATH if LEADERBOARD_PATH.is_file() else None,
            truth_path=Path(result.get("truth_path")) if result.get("truth_path") else None,
            result=result,
        )
    previous_score = _load_json(central_result_path) if central_result_path.is_file() and force else None

    if not submission_path.is_file():
        return ScoreRunResult(False, issues=[f"Submission file does not exist: {submission_path}"])

    try:
        truth_snapshot = create_source_truth_snapshot(run_dir, DEFAULT_TRUTH_DIR)
        truth_path = truth_snapshot.truth_dir / "latest_truth.json"
        truth = _load_json(truth_path)
        submission = _load_json(submission_path)
        _validate_matchday(submission, truth)
    except Exception as exc:
        return ScoreRunResult(False, issues=[f"Scoring setup failed: {exc}"])

    leaderboard = _load_leaderboard()
    if previous_score is not None:
        leaderboard = _remove_score_from_leaderboard(leaderboard, previous_score)
    leaderboard_entry = _leaderboard_lookup(leaderboard).get(
        submission["team_id"],
        {
            "team_id": submission["team_id"],
            "team_name": submission.get("team_name", submission["team_id"]),
            "total_points": INITIAL_TEAM_POINTS,
            "fantasy_points": 0,
            "risk_points": 0,
            "matchdays_played": 0,
        },
    )

    team_result = TeamClaimsScorer(truth).score_submission(submission, leaderboard_entry)
    score_result = _build_score_result(
        job_id=job_id,
        submission_path=submission_path,
        truth_path=truth_path,
        team_result=team_result,
        matchday_id=truth.get("matchday_id"),
    )
    updated_leaderboard = _update_leaderboard(leaderboard, team_result, _utc_now())

    _write_json(result_path, score_result)
    _write_json(central_result_path, score_result)
    _write_json(LEADERBOARD_PATH, updated_leaderboard)
    return ScoreRunResult(
        success=True,
        result_path=result_path,
        leaderboard_path=LEADERBOARD_PATH,
        truth_path=truth_path,
        result=score_result,
    )


def get_score_result(job_id: str) -> dict[str, Any] | None:
    central_path = SCORED_JOBS_DIR / f"{job_id}.score.json"
    if central_path.is_file():
        return _load_json(central_path)

    run_root = RUNS_ROOT / job_id
    if not run_root.is_dir():
        return None
    for path in sorted(run_root.glob("*/score_result.json")):
        return _load_json(path)
    return None


def list_score_results() -> list[dict[str, Any]]:
    if not SCORED_JOBS_DIR.is_dir():
        return []
    results = [_load_json(path) for path in sorted(SCORED_JOBS_DIR.glob("*.score.json"))]
    return sorted(results, key=lambda item: item.get("generated_at") or "", reverse=True)


def get_leaderboard() -> dict[str, Any]:
    return _load_leaderboard()


def score_existing_job(job_id: str, force: bool = False) -> ScoreRunResult:
    submission_path = _find_submission_path(job_id)
    if submission_path is None:
        return ScoreRunResult(False, issues=[f"No submission.json found for job id: {job_id}"])
    return score_codex_submission(
        job_id=job_id,
        submission_path=submission_path,
        run_dir=submission_path.parent,
        force=force,
    )


def _find_submission_path(job_id: str) -> Path | None:
    run_root = RUNS_ROOT / job_id
    if not run_root.is_dir():
        return None
    for path in sorted(run_root.glob("*/submission.json")):
        return path
    return None


def _build_score_result(
    *,
    job_id: str,
    submission_path: Path,
    truth_path: Path,
    team_result: dict[str, Any],
    matchday_id: str | None,
) -> dict[str, Any]:
    return {
        "schema_version": "fantasy-cup-score-result-v1",
        "generated_at": _utc_now(),
        "job_id": job_id,
        "matchday_id": matchday_id,
        "truth_path": str(truth_path),
        "submission_path": str(submission_path),
        "leaderboard_path": str(LEADERBOARD_PATH),
        "result": team_result,
    }


def _update_leaderboard(leaderboard: dict[str, Any], result: dict[str, Any], updated_at: str) -> dict[str, Any]:
    updated = {team_id: dict(entry) for team_id, entry in _leaderboard_lookup(leaderboard).items()}
    team_id = result["team_id"]
    entry = updated.setdefault(
        team_id,
        {
            "team_id": team_id,
            "team_name": result["team_name"],
            "total_points": INITIAL_TEAM_POINTS,
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
    for index, item in enumerate(teams, start=1):
        item["rank"] = index

    return {
        "schema_version": "fantasy-cup-leaderboard-v1",
        "updated_at": updated_at,
        "teams": teams,
    }


def _remove_score_from_leaderboard(leaderboard: dict[str, Any], score_result: dict[str, Any]) -> dict[str, Any]:
    old_result = score_result.get("result") or {}
    team_id = old_result.get("team_id")
    if not team_id:
        return leaderboard

    updated = {item["team_id"]: dict(item) for item in leaderboard.get("teams", []) if "team_id" in item}
    entry = updated.get(team_id)
    if entry is None:
        return leaderboard

    entry["total_points"] = round(float(entry.get("total_points", 0)) - float(old_result.get("total_delta", 0)), 2)
    entry["fantasy_points"] = round(float(entry.get("fantasy_points", 0)) - float(old_result.get("fantasy_points", 0)), 2)
    entry["risk_points"] = round(float(entry.get("risk_points", 0)) - float(old_result.get("risk_points", 0)), 2)
    entry["matchdays_played"] = max(0, int(entry.get("matchdays_played", 0)) - 1)

    teams = sorted(updated.values(), key=lambda item: (-float(item.get("total_points", 0)), item["team_name"]))
    for index, item in enumerate(teams, start=1):
        item["rank"] = index
    return {
        "schema_version": "fantasy-cup-leaderboard-v1",
        "updated_at": _utc_now(),
        "teams": teams,
    }


def _validate_matchday(submission: dict[str, Any], truth: dict[str, Any]) -> None:
    submission_matchday = submission.get("matchday_id")
    truth_matchday = truth.get("matchday_id")
    if submission_matchday and truth_matchday and submission_matchday != truth_matchday:
        raise ValueError(f"Submission matchday {submission_matchday!r} does not match truth {truth_matchday!r}.")
    if not truth.get("state", {}).get("complete", True):
        incomplete = ", ".join(truth.get("state", {}).get("incomplete_fixture_ids") or [])
        raise ValueError(f"Source truth is incomplete. Incomplete fixtures: {incomplete}")


def _load_leaderboard() -> dict[str, Any]:
    if LEADERBOARD_PATH.is_file():
        return _load_json(LEADERBOARD_PATH)
    return {
        "schema_version": "fantasy-cup-leaderboard-v1",
        "updated_at": None,
        "teams": [],
    }


def _leaderboard_lookup(leaderboard: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {entry["team_id"]: entry for entry in leaderboard.get("teams", []) if "team_id" in entry}


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any] | list[Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def copy_score_result_to_run(job_id: str, run_dir: Path) -> Path | None:
    """Best-effort helper for future run archival use."""
    source = SCORED_JOBS_DIR / f"{job_id}.score.json"
    if not source.is_file():
        return None
    destination = run_dir / "score_result.json"
    shutil.copy2(source, destination)
    return destination
