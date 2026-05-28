from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from functools import partial
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
APP_ROOT = Path(__file__).resolve().parent
SCORING_ROOT = ROOT / "scoring"
TRUTH_PATH = SCORING_ROOT / "truth_data" / "latest_truth.json"

DATA_ROOT = APP_ROOT / "data"
SUBMISSIONS_PATH = DATA_ROOT / "team_submissions.json"
LEADERBOARD_SEED_PATH = DATA_ROOT / "leaderboard_seed.json"
MATCHDAY_RESULTS_PATH = DATA_ROOT / "matchday_results.json"
LEADERBOARD_PATH = DATA_ROOT / "leaderboard.json"

sys.path.insert(0, str(ROOT))

from scoring.team_claims_scorer import TeamClaimsScorer  # noqa: E402


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict | list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_truth() -> dict:
    if not TRUTH_PATH.exists():
        raise FileNotFoundError(
            f"Missing truth file: {TRUTH_PATH}. Run scoring/daily_truth_pipeline.py before starting playtests."
        )
    return read_json(TRUTH_PATH)


def empty_submissions(truth: dict) -> dict:
    return {
        "schema_version": "fantasy-cup-team-claims-v1",
        "matchday_id": truth.get("matchday_id", "truth-test-world-cup-2022"),
        "submissions": [],
    }


def empty_leaderboard() -> dict:
    return {
        "schema_version": "fantasy-cup-leaderboard-v1",
        "updated_at": utc_now(),
        "teams": [],
    }


def ensure_data_files(truth: dict) -> None:
    DATA_ROOT.mkdir(parents=True, exist_ok=True)
    if not SUBMISSIONS_PATH.exists():
        write_json(SUBMISSIONS_PATH, empty_submissions(truth))
    if not LEADERBOARD_SEED_PATH.exists():
        write_json(LEADERBOARD_SEED_PATH, empty_leaderboard())


def read_optional_json(path: Path, fallback: dict) -> dict:
    if path.exists():
        return read_json(path)
    return fallback


def normalize_submission(payload: dict) -> tuple[dict, float]:
    team_id = str(payload.get("team_id", "")).strip()
    team_name = str(payload.get("team_name", team_id)).strip()
    if not team_id:
        raise ValueError("team_id is required")
    if not team_name:
        raise ValueError("team_name is required")

    try:
        previous_total = float(payload.get("previous_total_points", 100))
    except (TypeError, ValueError) as error:
        raise ValueError("previous_total_points must be numeric") from error

    answers = payload.get("answers", {})
    if not isinstance(answers, dict):
        raise ValueError("answers must be an object")

    return (
        {
            "team_id": team_id,
            "team_name": team_name,
            "submitted_at": utc_now(),
            "answers": answers,
        },
        previous_total,
    )


def upsert_submission(submissions: dict, submission: dict) -> dict:
    team_id = submission["team_id"]
    existing = [
        item for item in submissions.get("submissions", []) if str(item.get("team_id")) != team_id
    ]
    existing.append(submission)
    submissions["submissions"] = sorted(existing, key=lambda item: item["team_name"].lower())
    return submissions


def upsert_seed_team(leaderboard: dict, submission: dict, previous_total: float) -> dict:
    team_id = submission["team_id"]
    teams = [item for item in leaderboard.get("teams", []) if str(item.get("team_id")) != team_id]
    teams.append(
        {
            "rank": 0,
            "team_id": team_id,
            "team_name": submission["team_name"],
            "total_points": previous_total,
            "fantasy_points": 0,
            "risk_points": 0,
            "matchdays_played": 0,
        }
    )
    teams = sorted(teams, key=lambda item: (-float(item.get("total_points", 0)), item["team_name"].lower()))
    for index, item in enumerate(teams, start=1):
        item["rank"] = index
    leaderboard["updated_at"] = utc_now()
    leaderboard["teams"] = teams
    return leaderboard


def score_current_state(truth: dict, submissions: dict, seed_leaderboard: dict) -> tuple[dict, dict]:
    generated_at = utc_now()
    matchday_results, leaderboard = TeamClaimsScorer(truth).score_matchday(
        submissions,
        seed_leaderboard,
        generated_at,
    )
    matchday_results["truth_path"] = str(TRUTH_PATH)
    matchday_results["submissions_path"] = str(SUBMISSIONS_PATH)
    matchday_results["leaderboard_input_path"] = str(LEADERBOARD_SEED_PATH)
    write_json(MATCHDAY_RESULTS_PATH, matchday_results)
    write_json(LEADERBOARD_PATH, leaderboard)
    return matchday_results, leaderboard


def log(message: str) -> None:
    if sys.stdout:
        print(message, flush=True)


class PlaytestHandler(SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        if sys.stderr:
            super().log_message(format, *args)

    def do_GET(self) -> None:
        route = urlparse(self.path).path
        if route == "/api/state":
            self.handle_state()
            return
        if route == "/":
            self.path = "/index.html"
        super().do_GET()

    def do_POST(self) -> None:
        route = urlparse(self.path).path
        if route == "/api/submissions":
            self.handle_submission()
            return
        if route == "/api/reset":
            self.handle_reset()
            return
        self.send_error(HTTPStatus.NOT_FOUND, "Unknown API route")

    def handle_state(self) -> None:
        try:
            truth = load_truth()
            ensure_data_files(truth)
            seed = read_optional_json(LEADERBOARD_SEED_PATH, empty_leaderboard())
            response = {
                "truth": truth,
                "submissions": read_optional_json(SUBMISSIONS_PATH, empty_submissions(truth)),
                "leaderboard_seed": seed,
                "matchday_results": read_optional_json(MATCHDAY_RESULTS_PATH, {"results": []}),
                "leaderboard": read_optional_json(LEADERBOARD_PATH, seed),
                "paths": {
                    "truth": str(TRUTH_PATH),
                    "submissions": str(SUBMISSIONS_PATH),
                    "leaderboard_seed": str(LEADERBOARD_SEED_PATH),
                    "matchday_results": str(MATCHDAY_RESULTS_PATH),
                    "leaderboard": str(LEADERBOARD_PATH),
                },
            }
            self.send_json(response)
        except Exception as error:  # Keeps playtest failures visible in the browser.
            self.send_json({"error": str(error)}, status=HTTPStatus.INTERNAL_SERVER_ERROR)

    def handle_submission(self) -> None:
        try:
            truth = load_truth()
            ensure_data_files(truth)
            submission, previous_total = normalize_submission(self.read_request_json())
            submissions = upsert_submission(read_json(SUBMISSIONS_PATH), submission)
            seed = upsert_seed_team(read_json(LEADERBOARD_SEED_PATH), submission, previous_total)
            write_json(SUBMISSIONS_PATH, submissions)
            write_json(LEADERBOARD_SEED_PATH, seed)
            matchday_results, leaderboard = score_current_state(truth, submissions, seed)
            self.send_json(
                {
                    "submission": submission,
                    "submissions": submissions,
                    "matchday_results": matchday_results,
                    "leaderboard": leaderboard,
                }
            )
        except ValueError as error:
            self.send_json({"error": str(error)}, status=HTTPStatus.BAD_REQUEST)
        except Exception as error:
            self.send_json({"error": str(error)}, status=HTTPStatus.INTERNAL_SERVER_ERROR)

    def handle_reset(self) -> None:
        try:
            truth = load_truth()
            write_json(SUBMISSIONS_PATH, empty_submissions(truth))
            write_json(LEADERBOARD_SEED_PATH, empty_leaderboard())
            write_json(MATCHDAY_RESULTS_PATH, {"schema_version": "fantasy-cup-matchday-results-v1", "results": []})
            write_json(LEADERBOARD_PATH, empty_leaderboard())
            self.send_json({"ok": True})
        except Exception as error:
            self.send_json({"error": str(error)}, status=HTTPStatus.INTERNAL_SERVER_ERROR)

    def read_request_json(self) -> dict:
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)
        if not body:
            return {}
        return json.loads(body.decode("utf-8"))

    def send_json(self, payload: dict, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> int:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    handler = partial(PlaytestHandler, directory=str(APP_ROOT))
    ThreadingHTTPServer.allow_reuse_address = True
    with ThreadingHTTPServer(("127.0.0.1", port), handler) as server:
        log(f"Playtest app: http://127.0.0.1:{port}")
        log(f"Truth source: {TRUTH_PATH}")
        server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
