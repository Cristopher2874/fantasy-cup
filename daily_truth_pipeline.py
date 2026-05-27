from __future__ import annotations

import http.client
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlencode

# World Cup is league 1 in API-Football.
LEAGUE_ID = "1"
SEASON = "2022"
TIMEZONE = "UTC"

# "fixture_ids" and "date" for paid plan#
# Supported modes:
#   "fixture_ids" - fetch the explicit FIXTURE_IDS below.
#   "date"        - fetch fixture IDs for TARGET_DATE, then fetch each detail.
#   "season"      - fetch all season fixture IDs, then fetch each detail.
SOURCE_MODE = "fixture_ids"
TARGET_DATE = "2022-12-18"

#sample data
FIXTURE_IDS = [
    "855735",  # England 6-2 Iran: goals, assists, cards, starters, minutes.
    "855767",  # Canada 1-2 Morocco: own goal.
    "977345",  # Morocco 0-0 Spain: clean sheets, extra time, penalties.
    "978088",  # Morocco 1-0 Portugal: clean sheet, goalkeeper 3 saves.
    "979139",  # Argentina 3-3 France: final, extra time, penalties.
]

MATCHDAY_ID = "truth-test-world-cup-2022"
OUTPUT_ROOT = Path("truth_data")
WRITE_LATEST_COPY = True

POINT_RULES = {
    "starts": 2,
    "plays_60": 2,
    "goal": 6,
    "assist": 4,
    "clean_sheet": 4,
    "goalkeeper_saves": 2,
    "yellow_card": -1,
    "red_card": -3,
    "own_goal": -3,
}

RISK_CLAIM_CAPABILITIES = {
    "match_2plus_goals": {
        "category": "green",
        "required_fields": ["match_id"],
        "api_status": "supported",
        "source": "fixture final goals",
    },
    "no_goal_first_10": {
        "category": "green",
        "required_fields": ["match_id"],
        "api_status": "supported",
        "source": "goal events with elapsed minute",
    },
    "goal_before_halftime": {
        "category": "green",
        "required_fields": ["match_id"],
        "api_status": "supported",
        "source": "goal events with first-half timing",
    },
    "match_2plus_cards": {
        "category": "green",
        "required_fields": ["match_id"],
        "api_status": "supported",
        "source": "card events",
    },
    "no_goal_stoppage_time": {
        "category": "green",
        "required_fields": ["match_id"],
        "api_status": "supported",
        "source": "goal events with time.extra",
    },
    "both_teams_score": {
        "category": "yellow",
        "required_fields": ["match_id"],
        "api_status": "supported",
        "source": "fixture final goals",
    },
    "match_over_2_5_goals": {
        "category": "yellow",
        "required_fields": ["match_id"],
        "api_status": "supported",
        "source": "fixture final goals",
    },
    "team_scores_first": {
        "category": "yellow",
        "required_fields": ["match_id", "team_id"],
        "api_status": "supported",
        "source": "first credited non-shootout goal event",
    },
    "player_scores": {
        "category": "yellow",
        "required_fields": ["match_id", "player_id"],
        "api_status": "supported",
        "source": "non-own, non-shootout goal events",
    },
    "match_2plus_yellow_cards": {
        "category": "yellow",
        "required_fields": ["match_id"],
        "api_status": "supported",
        "source": "yellow-card events",
    },
    "exact_score": {
        "category": "red",
        "required_fields": ["match_id", "home_score", "away_score"],
        "api_status": "supported",
        "source": "fixture final goals, excluding shootout score",
    },
    "player_scores_2plus": {
        "category": "red",
        "required_fields": ["match_id", "player_id"],
        "api_status": "supported",
        "source": "non-own, non-shootout goal events",
    },
    "team_wins_by_3plus": {
        "category": "red",
        "required_fields": ["match_id", "team_id"],
        "api_status": "supported",
        "source": "fixture final goals, excluding shootout score",
    },
    "team_comeback_win": {
        "category": "red",
        "required_fields": ["match_id", "team_id"],
        "api_status": "supported",
        "source": "first goal event plus final goals",
    },
    "red_card_shown": {
        "category": "red",
        "required_fields": ["match_id"],
        "api_status": "supported",
        "source": "red-card and second-yellow-red events",
    },
    "match_goes_to_extra_time": {
        "category": "red",
        "required_fields": ["match_id"],
        "api_status": "supported_knockout_only",
        "source": "fixture status and extra-time score fields",
    },
    "match_goes_to_penalties": {
        "category": "red",
        "required_fields": ["match_id"],
        "api_status": "supported_knockout_only",
        "source": "fixture status and penalty score fields",
    },
}

FANTASY_SCORING_CAPABILITIES = {
    "starts": "supported from player match statistics games.substitute and minutes",
    "plays_60": "supported from player match statistics games.minutes",
    "goal": "supported from player match statistics goals.total",
    "assist": "supported from player match statistics goals.assists",
    "clean_sheet": "derived from final goals conceded plus player position/minutes",
    "goalkeeper_saves": "supported from player match statistics goals.saves",
    "yellow_card": "supported from player match statistics cards.yellow",
    "red_card": "supported from player match statistics cards.red",
    "own_goal": "supported from fixture events detail=Own Goal",
}


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


def normalize_position(position: str | None) -> str | None:
    if not position:
        return None
    value = position.lower()
    if value in {"g", "goalkeeper"}:
        return "GK"
    if value in {"d", "defender"}:
        return "DEF"
    if value in {"m", "midfielder"}:
        return "MID"
    if value in {"f", "attacker", "forward"}:
        return "FWD"
    return position


def int_value(value) -> int:
    return int(value or 0)


def team_goals_conceded(fixture: dict, team_id: str) -> int:
    home_id = str(fixture["teams"]["home"]["id"])
    goals = fixture.get("goals") or {}
    if team_id == home_id:
        return int_value(goals.get("away"))
    return int_value(goals.get("home"))


def score_player(player_truth: dict) -> tuple[int, list[dict]]:
    points = 0
    breakdown = []

    def add(label: str, value: int) -> None:
        nonlocal points
        if value:
            points += value
            breakdown.append({"label": label, "points": value})

    add("Started", POINT_RULES["starts"] if player_truth["events"]["starts"] else 0)
    add("Played 60+ minutes", POINT_RULES["plays_60"] if player_truth["events"]["minutes"] >= 60 else 0)
    add("Goals", player_truth["events"]["goals"] * POINT_RULES["goal"])
    add("Assists", player_truth["events"]["assists"] * POINT_RULES["assist"])
    add("Clean sheet", POINT_RULES["clean_sheet"] if player_truth["events"]["clean_sheet"] else 0)
    add("Goalkeeper 3+ saves", POINT_RULES["goalkeeper_saves"] if player_truth["events"]["saves"] >= 3 else 0)
    add("Yellow cards", player_truth["events"]["yellow_cards"] * POINT_RULES["yellow_card"])
    add("Red cards", player_truth["events"]["red_cards"] * POINT_RULES["red_card"])
    add("Own goals", player_truth["events"]["own_goals"] * POINT_RULES["own_goal"])
    return points, breakdown


def is_card_event(event: dict) -> bool:
    return str(event.get("type", "")).lower() == "card"


def is_yellow_card(event: dict) -> bool:
    return is_card_event(event) and str(event.get("detail", "")).lower() == "yellow card"


def is_red_card(event: dict) -> bool:
    detail = str(event.get("detail", "")).lower()
    return is_card_event(event) and ("red card" in detail or "second yellow" in detail)


def is_goal_event(event: dict) -> bool:
    detail = str(event.get("detail", "")).lower()
    return str(event.get("type", "")).lower() == "goal" and detail != "missed penalty"


def is_own_goal(event: dict) -> bool:
    return is_goal_event(event) and "own goal" in str(event.get("detail", "")).lower()


def is_penalty_shootout_goal(event: dict, fixture: dict) -> bool:
    status = str(fixture.get("fixture", {}).get("status", {}).get("short", "")).upper()
    detail = str(event.get("detail", "")).lower()
    elapsed = int_value((event.get("time") or {}).get("elapsed"))
    return status == "PEN" and "penalty" in detail and elapsed >= 120


def countable_goal_events(fixture: dict) -> list[dict]:
    return [
        event
        for event in fixture.get("events", []) or []
        if is_goal_event(event) and not is_penalty_shootout_goal(event, fixture)
    ]


def non_own_countable_goal_events(fixture: dict) -> list[dict]:
    return [event for event in countable_goal_events(fixture) if not is_own_goal(event)]


def parse_players(fixture: dict) -> dict[str, dict]:
    own_goals_by_player: dict[str, int] = {}
    for event in fixture.get("events", []) or []:
        if is_own_goal(event):
            player_id = str((event.get("player") or {}).get("id") or "")
            if player_id:
                own_goals_by_player[player_id] = own_goals_by_player.get(player_id, 0) + 1

    players: dict[str, dict] = {}
    for team_block in fixture.get("players", []) or []:
        team = team_block.get("team") or {}
        team_id = str(team.get("id"))
        for player_block in team_block.get("players", []) or []:
            player = player_block.get("player") or {}
            stats = (player_block.get("statistics") or [{}])[0] or {}
            games = stats.get("games") or {}
            goals = stats.get("goals") or {}
            cards = stats.get("cards") or {}
            position = normalize_position(games.get("position"))
            minutes = int_value(games.get("minutes"))
            starts = bool(minutes and games.get("substitute") is False)
            clean_sheet = bool(
                position in {"GK", "DEF"}
                and minutes >= 60
                and team_goals_conceded(fixture, team_id) == 0
            )
            player_id = str(player.get("id"))
            truth = {
                "id": player_id,
                "name": player.get("name"),
                "team_id": team_id,
                "team": team.get("name"),
                "position": position,
                "match_id": str(fixture["fixture"]["id"]),
                "events": {
                    "starts": starts,
                    "minutes": minutes,
                    "goals": int_value(goals.get("total")),
                    "assists": int_value(goals.get("assists")),
                    "clean_sheet": clean_sheet,
                    "saves": int_value(goals.get("saves")),
                    "yellow_cards": int_value(cards.get("yellow")),
                    "red_cards": int_value(cards.get("red")),
                    "own_goals": own_goals_by_player.get(player_id, 0),
                },
            }
            points, breakdown = score_player(truth)
            truth["fantasy_points"] = points
            truth["fantasy_breakdown"] = breakdown
            players[player_id] = truth
    return players


def final_goals(fixture: dict) -> tuple[int, int]:
    goals = fixture.get("goals") or {}
    return int_value(goals.get("home")), int_value(goals.get("away"))


def winner_team_id(fixture: dict) -> str | None:
    home_goals, away_goals = final_goals(fixture)
    home = fixture["teams"]["home"]
    away = fixture["teams"]["away"]
    if home_goals > away_goals:
        return str(home["id"])
    if away_goals > home_goals:
        return str(away["id"])

    penalty = fixture.get("score", {}).get("penalty") or {}
    home_penalties = penalty.get("home")
    away_penalties = penalty.get("away")
    if home_penalties is None or away_penalties is None:
        return None
    if home_penalties > away_penalties:
        return str(home["id"])
    if away_penalties > home_penalties:
        return str(away["id"])
    return None


def went_to_extra_time(fixture: dict) -> bool:
    status = str(fixture.get("fixture", {}).get("status", {}).get("short", "")).upper()
    extratime = fixture.get("score", {}).get("extratime") or {}
    return status in {"AET", "PEN"} or extratime.get("home") is not None or extratime.get("away") is not None


def went_to_penalties(fixture: dict) -> bool:
    status = str(fixture.get("fixture", {}).get("status", {}).get("short", "")).upper()
    penalty = fixture.get("score", {}).get("penalty") or {}
    return status == "PEN" or penalty.get("home") is not None or penalty.get("away") is not None


def parse_risk_truth(fixture: dict) -> dict:
    home = fixture["teams"]["home"]
    away = fixture["teams"]["away"]
    home_id = str(home["id"])
    away_id = str(away["id"])
    home_goals, away_goals = final_goals(fixture)
    total_goals = home_goals + away_goals
    countable_goals = countable_goal_events(fixture)
    non_own_goals = non_own_countable_goal_events(fixture)
    card_events = [event for event in fixture.get("events", []) or [] if is_card_event(event)]
    yellow_cards = [event for event in fixture.get("events", []) or [] if is_yellow_card(event)]
    red_cards = [event for event in fixture.get("events", []) or [] if is_red_card(event)]
    first_goal = countable_goals[0] if countable_goals else None
    first_goal_team_id = str((first_goal.get("team") or {}).get("id")) if first_goal else None

    player_goal_counts: dict[str, int] = {}
    for event in non_own_goals:
        player_id = str((event.get("player") or {}).get("id") or "")
        if player_id:
            player_goal_counts[player_id] = player_goal_counts.get(player_id, 0) + 1

    team_goal_diff = {
        home_id: home_goals - away_goals,
        away_id: away_goals - home_goals,
    }
    team_final_goals = {home_id: home_goals, away_id: away_goals}
    opponent_final_goals = {home_id: away_goals, away_id: home_goals}

    team_truth = {}
    for team_id in [home_id, away_id]:
        team_truth[team_id] = {
            "scores_first": first_goal_team_id == team_id,
            "wins_by_3plus": team_goal_diff[team_id] >= 3,
            "comeback_win": (
                first_goal_team_id is not None
                and first_goal_team_id != team_id
                and team_final_goals[team_id] > opponent_final_goals[team_id]
            ),
            "is_winner": winner_team_id(fixture) == team_id,
            "final_goals": team_final_goals[team_id],
        }

    player_truth = {
        player_id: {
            "non_own_goals": count,
            "scores": count >= 1,
            "scores_2plus": count >= 2,
        }
        for player_id, count in sorted(player_goal_counts.items())
    }

    goal_in_first_10 = any(1 <= int_value((event.get("time") or {}).get("elapsed")) <= 10 for event in countable_goals)
    goal_before_halftime = any(int_value((event.get("time") or {}).get("elapsed")) <= 45 for event in countable_goals)
    goal_in_stoppage_time = any((event.get("time") or {}).get("extra") is not None for event in countable_goals)

    return {
        "match_claims": {
            "match_2plus_goals": total_goals >= 2,
            "no_goal_first_10": not goal_in_first_10,
            "goal_before_halftime": goal_before_halftime,
            "match_2plus_cards": len(card_events) >= 2,
            "no_goal_stoppage_time": not goal_in_stoppage_time,
            "both_teams_score": home_goals >= 1 and away_goals >= 1,
            "match_over_2_5_goals": total_goals >= 3,
            "match_2plus_yellow_cards": len(yellow_cards) >= 2,
            "red_card_shown": len(red_cards) >= 1,
            "match_goes_to_extra_time": went_to_extra_time(fixture),
            "match_goes_to_penalties": went_to_penalties(fixture),
        },
        "parameterized_claims": {
            "exact_score": {"home_score": home_goals, "away_score": away_goals},
            "team_scores_first": {team_id: value["scores_first"] for team_id, value in team_truth.items()},
            "team_wins_by_3plus": {team_id: value["wins_by_3plus"] for team_id, value in team_truth.items()},
            "team_comeback_win": {team_id: value["comeback_win"] for team_id, value in team_truth.items()},
            "player_scores": {player_id: value["scores"] for player_id, value in player_truth.items()},
            "player_scores_2plus": {player_id: value["scores_2plus"] for player_id, value in player_truth.items()},
        },
        "evidence": {
            "total_goals": total_goals,
            "countable_goal_events": len(countable_goals),
            "card_events": len(card_events),
            "yellow_card_events": len(yellow_cards),
            "red_card_events": len(red_cards),
            "first_goal": summarize_event(first_goal) if first_goal else None,
            "team_truth": team_truth,
            "player_goal_counts": player_goal_counts,
        },
    }


def summarize_event(event: dict) -> dict:
    return {
        "elapsed": (event.get("time") or {}).get("elapsed"),
        "extra": (event.get("time") or {}).get("extra"),
        "team_id": str((event.get("team") or {}).get("id")),
        "team": (event.get("team") or {}).get("name"),
        "player_id": str((event.get("player") or {}).get("id")),
        "player": (event.get("player") or {}).get("name"),
        "type": event.get("type"),
        "detail": event.get("detail"),
    }


def parse_match(fixture: dict) -> tuple[dict, dict[str, dict]]:
    home = fixture["teams"]["home"]
    away = fixture["teams"]["away"]
    home_goals, away_goals = final_goals(fixture)
    players = parse_players(fixture)
    match = {
        "id": str(fixture["fixture"]["id"]),
        "provider": "api-football",
        "provider_fixture_id": fixture["fixture"]["id"],
        "round": fixture.get("league", {}).get("round"),
        "stage": "knockout" if not str(fixture.get("league", {}).get("round", "")).startswith("Group Stage") else "league",
        "kickoff": fixture["fixture"].get("date"),
        "status": fixture["fixture"].get("status"),
        "home_team": {
            "id": str(home["id"]),
            "name": home.get("name"),
            "winner": home.get("winner"),
        },
        "away_team": {
            "id": str(away["id"]),
            "name": away.get("name"),
            "winner": away.get("winner"),
        },
        "score": {
            "home": home_goals,
            "away": away_goals,
            "fulltime": fixture.get("score", {}).get("fulltime"),
            "extratime": fixture.get("score", {}).get("extratime"),
            "penalty": fixture.get("score", {}).get("penalty"),
            "winner_team_id": winner_team_id(fixture),
            "went_to_extra_time": went_to_extra_time(fixture),
            "went_to_penalties": went_to_penalties(fixture),
        },
        "api_data_presence": {
            "events": bool(fixture.get("events")),
            "lineups": bool(fixture.get("lineups")),
            "fixture_statistics": bool(fixture.get("statistics")),
            "player_statistics": bool(fixture.get("players")),
        },
        "risk_truth": parse_risk_truth(fixture),
    }
    return match, players


def normalize_truth(raw_data: dict) -> dict:
    matches = []
    player_records = []

    for payload in raw_data["fixtures"]:
        for fixture in payload.get("response", []) or []:
            match, players = parse_match(fixture)
            matches.append(match)
            for player in players.values():
                player["record_id"] = f"{player['match_id']}:{player['id']}"
                player_records.append(player)

    matches.sort(key=lambda item: item.get("kickoff") or "")
    player_records.sort(key=lambda item: (item["match_id"], item["team"] or "", item["name"] or ""))
    return {
        "schema_version": "fantasy-cup-truth-v1",
        "generated_at": utc_now(),
        "matchday_id": MATCHDAY_ID,
        "source": {
            "provider": "api-football",
            "league_id": LEAGUE_ID,
            "season": SEASON,
            "source_mode": SOURCE_MODE,
            "target_date": TARGET_DATE if SOURCE_MODE == "date" else None,
            "fixture_ids": raw_data["fixture_ids"],
        },
        "capabilities": {
            "fantasy_scoring": FANTASY_SCORING_CAPABILITIES,
            "risk_claims": RISK_CLAIM_CAPABILITIES,
            "app_owned_not_from_api": [
                "team registrations",
                "agent submissions",
                "fantasy xi selections",
                "risk-play selection by each team",
                "team score before matchday",
                "stake calculation",
                "organizer review overrides",
                "bracket pick locking",
            ],
        },
        "point_rules": POINT_RULES,
        "matches": matches,
        "players": player_records,
    }


def run_pipeline() -> tuple[Path, Path]:
    api_key = resolve_api_key()
    if not api_key:
        raise RuntimeError("API key is not configured. Set API_KEY in this file or APISPORTS_KEY in .env.")

    run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    raw_data = fetch_raw_data(api_key)
    truth = normalize_truth(raw_data)

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
