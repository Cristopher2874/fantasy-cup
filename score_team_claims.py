from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from team_claims_scorer import TeamClaimsScorer


TRUTH_PATH = Path("truth_data/latest_truth.json")
SUBMISSIONS_PATH = Path("mock_team_claims_2022.json")
LEADERBOARD_PATH = Path("mock_leaderboard_2022.json")
OUTPUT_DIR = Path("score_data")

MATCHDAY_RESULTS_PATH = OUTPUT_DIR / "matchday_results.json"
UPDATED_LEADERBOARD_PATH = OUTPUT_DIR / "leaderboard.json"


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict | list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run_scoring() -> tuple[Path, Path]:
    truth = load_json(TRUTH_PATH)
    submissions = load_json(SUBMISSIONS_PATH)
    leaderboard = load_json(LEADERBOARD_PATH)
    generated_at = utc_now()

    matchday_results, updated_leaderboard = TeamClaimsScorer(truth).score_matchday(
        submissions,
        leaderboard,
        generated_at,
    )
    matchday_results["truth_path"] = str(TRUTH_PATH)
    matchday_results["submissions_path"] = str(SUBMISSIONS_PATH)
    matchday_results["leaderboard_input_path"] = str(LEADERBOARD_PATH)

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
