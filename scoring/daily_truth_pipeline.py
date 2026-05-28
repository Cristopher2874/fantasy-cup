import http.client
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlencode
from dotenv import load_dotenv
load_dotenv()

try:
    from scoring.truth_parser import FootballTruthParser
except ModuleNotFoundError:  # Allows `python scoring/daily_truth_pipeline.py`.
    from truth_parser import FootballTruthParser

# World Cup is league 1 in API-Football.
LEAGUE_ID = "1"
SEASON = "2022"
TIMEZONE = "UTC"

# "fixture_ids" is the best Free-plan test mode because rich fixture detail is
# available with individual id= calls. For production daily runs, use "date".
#
# Supported modes:
#   "fixture_ids" - fetch the explicit FIXTURE_IDS below.
#   "date"        - fetch fixture IDs for TARGET_DATE, then fetch each detail.
#   "season"      - fetch all season fixture IDs, then fetch each detail.
SOURCE_MODE = "fixture_ids"
TARGET_DATE = "2022-12-18"

# Free-plan-friendly fixture IDs that exercise scoring edge cases.
FIXTURE_IDS = [
    "855735",  # England 6-2 Iran: goals, assists, cards, starters, minutes.
    "855767",  # Canada 1-2 Morocco: own goal.
    "976534",  # England 3-0 Senegal: knockout clean sheet.
    "977345",  # Morocco 0-0 Spain: clean sheets, extra time, penalties.
    "978088",  # Morocco 1-0 Portugal: clean sheet, goalkeeper 3 saves.
    "979139",  # Argentina 3-3 France: final, extra time, penalties.
]

MATCHDAY_ID = "truth-test-world-cup-2022"
SCORING_ROOT = Path(__file__).resolve().parent
OUTPUT_ROOT = SCORING_ROOT / "truth_data"
WRITE_LATEST_COPY = True

def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")

def write_json(path: Path, payload: dict | list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

def build_query(params: dict[str, str | int | None]) -> str:
    clean_params = {key: value for key, value in params.items() if value is not None}
    return urlencode(clean_params)

def call_api(endpoint: str, params: dict[str, str | int | None], api_key: str) -> dict:
    path = endpoint if endpoint.startswith("/") else f"/{endpoint}"
    query = build_query(params)
    if query:
        path = f"{path}?{query}"

    connection = http.client.HTTPSConnection("v3.football.api-sports.io")
    try:
        connection.request("GET", path, headers={"x-apisports-key": api_key})
        response = connection.getresponse()
        body = response.read().decode("utf-8")
    finally:
        connection.close()

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        payload = {
            "errors": {"response": "API did not return valid JSON"},
            "status": response.status,
            "body": body,
        }
    payload["_request"] = {"endpoint": endpoint.strip("/"), "params": params}
    return payload

def response_errors(payload: dict) -> bool:
    errors = payload.get("errors")
    return bool(errors and errors != [])

def fetch_fixture_ids(api_key: str) -> list[str]:
    if SOURCE_MODE == "fixture_ids":
        return [str(item) for item in FIXTURE_IDS]

    if SOURCE_MODE == "date":
        payload = call_api(
            "fixtures",
            {"league": LEAGUE_ID, "season": SEASON, "date": TARGET_DATE, "timezone": TIMEZONE},
            api_key,
        )
    elif SOURCE_MODE == "season":
        payload = call_api("fixtures", {"league": LEAGUE_ID, "season": SEASON, "timezone": TIMEZONE}, api_key)
    else:
        raise ValueError(f"Unknown SOURCE_MODE: {SOURCE_MODE}")

    if response_errors(payload):
        raise RuntimeError(f"Could not fetch fixture list: {payload.get('errors')}")

    return [str(item["fixture"]["id"]) for item in payload.get("response", [])]

def fetch_raw_data(api_key: str) -> dict:
    fixture_ids = fetch_fixture_ids(api_key)
    fixture_payloads = []
    for fixture_id in fixture_ids:
        payload = call_api("fixtures", {"id": fixture_id, "timezone": TIMEZONE}, api_key)
        if response_errors(payload):
            raise RuntimeError(f"Could not fetch fixture {fixture_id}: {payload.get('errors')}")
        fixture_payloads.append(payload)

    coverage = call_api("leagues", {"id": LEAGUE_ID, "season": SEASON}, api_key)

    return {
        "fetched_at": utc_now(),
        "source_mode": SOURCE_MODE,
        "league_id": LEAGUE_ID,
        "season": SEASON,
        "target_date": TARGET_DATE if SOURCE_MODE == "date" else None,
        "fixture_ids": fixture_ids,
        "coverage": coverage,
        "fixtures": fixture_payloads,
    }

def build_parser() -> FootballTruthParser:
    return FootballTruthParser(
        matchday_id=MATCHDAY_ID,
        league_id=LEAGUE_ID,
        season=SEASON,
        source_mode=SOURCE_MODE,
        target_date=TARGET_DATE,
    )

def run_pipeline() -> tuple[Path, Path]:
    api_key = os.getenv("APISPORTS_KEY", "").strip()

    run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    raw_data = fetch_raw_data(api_key)
    truth = build_parser().normalize(raw_data, generated_at=utc_now())

    raw_path = OUTPUT_ROOT / "raw" / run_id / "api_football_raw.json"
    truth_path = OUTPUT_ROOT / "final" / f"{MATCHDAY_ID}.truth.json"
    write_json(raw_path, raw_data)
    write_json(truth_path, truth)
    if WRITE_LATEST_COPY:
        write_json(OUTPUT_ROOT / "latest_truth.json", truth)

    return raw_path, truth_path

def main() -> int:
    try:
        raw_path, truth_path = run_pipeline()
    except Exception as error:
        print(f"Daily truth pipeline failed: {error}", file=sys.stderr)
        return 1

    print(f"Raw API data: {raw_path}")
    print(f"Normalized truth: {truth_path}")
    if WRITE_LATEST_COPY:
        print(f"Latest copy: {OUTPUT_ROOT / 'latest_truth.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
