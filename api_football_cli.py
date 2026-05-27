from __future__ import annotations

import http.client
import json
import os
import sys
from pathlib import Path
from urllib.parse import urlencode

API_KEY = ""

# Request snippet.
#
# Examples:
#   ENDPOINT = "countries"
#   QUERY_PARAMS = {}
#
# ENDPOINT = "leagues"
# QUERY_PARAMS = {"country": "Mexico", "season": "2024"}
#
# ENDPOINT = "fixtures"
# QUERY_PARAMS = {"league": "262", "season": "2024"}
#
ENDPOINT = "players"
QUERY_PARAMS = {"team": "2287", "season": "2024"}

# ENDPOINT = "leagues"
# QUERY_PARAMS = {"id": "262", "season": "2022"}

SELECTED_EXAMPLE: str | None = None

API_TEST_EXAMPLES: dict[str, tuple[str, dict[str, str]]] = {
    "world_cup_2022_coverage": (
        "leagues",
        {"id": "1", "season": "2022"},
    ),
    "world_cup_2022_all_fixtures": (
        "fixtures",
        {"league": "1", "season": "2022"},
    ),
    "world_cup_2022_england_iran": (
        "fixtures",
        {"id": "855735"},
    ),
    "world_cup_2022_canada_morocco_own_goal": (
        "fixtures",
        {"id": "855767"},
    ),
    "world_cup_2022_morocco_spain_penalties": (
        "fixtures",
        {"id": "977345"},
    ),
    "world_cup_2022_morocco_portugal_clean_sheet": (
        "fixtures",
        {"id": "978088"},
    ),
    "world_cup_2022_argentina_france_final": (
        "fixtures",
        {"id": "979139"},
    ),
}

# Optional: save the JSON response to a file as well as printing it.
OUTPUT_PATH: Path | None = None
# OUTPUT_PATH = Path("data/source/api-sports/manual-response.json")


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def resolve_api_key() -> str:
    load_dotenv(Path(__file__).resolve().parent / ".env")
    return API_KEY.strip() or os.getenv("APISPORTS_KEY", "").strip()


def build_query(params: dict[str, str | int | None]) -> str:
    clean_params = {key: value for key, value in params.items() if value is not None}
    return urlencode(clean_params)


def resolve_request() -> tuple[str, dict[str, str | int | None]]:
    if not SELECTED_EXAMPLE:
        return ENDPOINT, QUERY_PARAMS

    if SELECTED_EXAMPLE not in API_TEST_EXAMPLES:
        options = ", ".join(sorted(API_TEST_EXAMPLES))
        raise ValueError(f"Unknown SELECTED_EXAMPLE '{SELECTED_EXAMPLE}'. Options: {options}")

    return API_TEST_EXAMPLES[SELECTED_EXAMPLE]


def call_api(endpoint: str, query: str, api_key: str) -> dict:
    path = endpoint if endpoint.startswith("/") else f"/{endpoint}"
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
        return json.loads(body)
    except json.JSONDecodeError:
        return {
            "errors": {"response": "API did not return valid JSON"},
            "status": response.status,
            "body": body,
        }


def main() -> int:
    api_key = resolve_api_key()
    if not api_key:
        print(
            "API key is not configured. Set API_KEY at the top of this file, or add APISPORTS_KEY to .env.",
            file=sys.stderr,
        )
        return 2

    try:
        endpoint, params = resolve_request()
    except ValueError as error:
        print(error, file=sys.stderr)
        return 2

    endpoint = endpoint.strip("/")
    query = build_query(params)
    payload = call_api(endpoint, query, api_key)
    output = json.dumps(payload, indent=2, sort_keys=True)

    if OUTPUT_PATH:
        OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT_PATH.write_text(output + "\n", encoding="utf-8")

    print(output)
    return 1 if payload.get("errors") else 0


if __name__ == "__main__":
    raise SystemExit(main())
