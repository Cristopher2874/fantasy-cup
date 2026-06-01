from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from services.codex_runner.skill_runner import validate_submission_contract
from services.score_engine import TeamClaimsScorer


def _player(record_id: str, player_id: str, position: str, points: int) -> dict[str, object]:
    return {
        "record_id": record_id,
        "match_id": "match-1",
        "id": player_id,
        "name": f"Player {player_id}",
        "team": "Fun FC",
        "position": position,
        "fantasy_points": points,
        "fantasy_breakdown": [],
    }


class FantasyXiFlexibilityTest(unittest.TestCase):
    def test_scorer_allows_repeated_all_in_pick(self) -> None:
        truth = {"players": [_player("match-1:p1", "p1", "FWD", 7)]}
        fantasy_xi = [{"record_id": "match-1:p1"} for _ in range(11)]

        result = TeamClaimsScorer(truth).validate_and_score_fantasy_xi(fantasy_xi)

        self.assertTrue(result["valid"])
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["points"], 77)
        self.assertEqual(result["position_counts"]["FWD"], 11)

    def test_scorer_still_allows_traditional_xi(self) -> None:
        positions = ["GK", "DEF", "DEF", "DEF", "MID", "MID", "MID", "FWD", "FWD", "FWD", "FWD"]
        players = [
            _player(f"match-1:p{index}", f"p{index}", position, 1)
            for index, position in enumerate(positions, start=1)
        ]
        fantasy_xi = [{"record_id": player["record_id"]} for player in players]

        result = TeamClaimsScorer({"players": players}).validate_and_score_fantasy_xi(fantasy_xi)

        self.assertTrue(result["valid"])
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["points"], 11)
        self.assertEqual(result["position_counts"]["GK"], 1)
        self.assertEqual(result["position_counts"]["FWD"], 4)

    def test_submission_checker_allows_repeated_record_ids(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            public_data_dir = Path(temp_dir)
            (public_data_dir / "players.json").write_text(
                json.dumps([{"record_id": "match-1:p1"}]),
                encoding="utf-8",
            )
            submission = {
                "team_id": "team-fun",
                "team_name": "Team Fun",
                "matchday_id": "matchday-1",
                "answers": {
                    "fantasy_xi": [{"record_id": "match-1:p1"} for _ in range(11)],
                    "risk_play": None,
                    "strategy_summary": "All in on one player.",
                },
            }

            issues = validate_submission_contract(submission, public_data_dir)

        self.assertEqual(issues, [])


if __name__ == "__main__":
    unittest.main()
