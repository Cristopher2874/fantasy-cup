from __future__ import annotations

from typing import Any

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

class TeamClaimsScorer:
    def __init__(self, truth: dict) -> None:
        self.truth = truth
        players = truth.get("players", [])
        matches = truth.get("matches", [])
        self.match_by_id = {str(match["id"]): match for match in matches}
        self.player_by_record_id = {player["record_id"]: player for player in players}
        self.records_by_player_id: dict[str, list[dict]] = {}
        for player in players:
            self.records_by_player_id.setdefault(str(player["id"]), []).append(player)
        self.risk_capabilities = truth.get("capabilities", {}).get("risk_claims", {})

    def score_matchday(self, submissions: dict, leaderboard: dict, generated_at: str) -> tuple[dict, dict]:
        entries = self.leaderboard_lookup(leaderboard)
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
            results.append(self.score_submission(submission, leaderboard_entry))

        matchday_results = {
            "schema_version": "fantasy-cup-matchday-results-v1",
            "generated_at": generated_at,
            "matchday_id": submissions.get("matchday_id", self.truth.get("matchday_id")),
            "results": results,
        }
        updated_leaderboard = self.update_leaderboard(leaderboard, results, generated_at)
        return matchday_results, updated_leaderboard

    def score_submission(self, submission: dict, leaderboard_entry: dict) -> dict:
        answers = submission.get("answers", {})
        previous_total = float(leaderboard_entry.get("total_points", 0))
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

    def validate_and_score_fantasy_xi(self, fantasy_xi: Any) -> dict:
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

    def validate_and_score_risk_play(self, risk_play: Any, previous_total: float) -> dict:
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

    def resolve_player_selection(self, selection: Any) -> tuple[dict | None, str | None]:
        if isinstance(selection, str):
            if ":" in selection:
                player = self.player_by_record_id.get(selection)
                return player, None if player else f"Unknown player record_id: {selection}"

            records = self.records_by_player_id.get(selection, [])
            if len(records) == 1:
                return records[0], None
            if not records:
                return None, f"Unknown player_id: {selection}"
            return None, f"Ambiguous bare player_id {selection}; use record_id or match_id/player_id"

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

    def resolve_risk_outcome(self, risk_play: dict, match: dict) -> tuple[bool | None, str]:
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

    def update_leaderboard(self, leaderboard: dict, results: list[dict], updated_at: str) -> dict:
        existing = self.leaderboard_lookup(leaderboard)
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
            "updated_at": updated_at,
            "teams": teams,
        }

    @staticmethod
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

    @staticmethod
    def validate_required_fields(risk_play: dict, required_fields: list[str]) -> list[str]:
        missing = []
        for field in required_fields:
            if field not in risk_play or risk_play.get(field) in {None, ""}:
                missing.append(field)
        return missing

    @staticmethod
    def leaderboard_lookup(leaderboard: dict) -> dict[str, dict]:
        return {entry["team_id"]: entry for entry in leaderboard.get("teams", [])}
