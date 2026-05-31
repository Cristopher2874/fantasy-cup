"""Generate public matchday data for Codex skill execution.

This module is standalone inside ``inno-fantasy``. It calls API-Football,
persists raw responses for replay/debugging, and writes the static public data
bundle consumed by uploaded skills.
"""
from __future__ import annotations

import argparse
import hashlib
import http.client
import json
import os
import shutil
import time
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

from config.config_provider import GlobalConfigProvider


BACKEND_ROOT = Path(__file__).resolve().parents[2]
INNO_ROOT = BACKEND_ROOT.parent
DATA_ROOT = INNO_ROOT / "data"

CONFIG = GlobalConfigProvider()
DEFAULT_LEAGUE_ID = CONFIG.get_str("game", "default_league_id", "1")
DEFAULT_SEASON = CONFIG.get_str("game", "default_season", "2022")
DEFAULT_PUBLIC_DATA_DIR = DATA_ROOT / "public_data"
DEFAULT_RAW_SOURCE_DIR = DATA_ROOT / "source" / "api-football"
DEFAULT_SCHEMA_PATH = BACKEND_ROOT / "models" / "team_submission.schema.json"

PUBLIC_DATA_FILES = (
    "manifest.json",
    "matchday.json",
    "matchdays_index.json",
    "matches.json",
    "teams.json",
    "players.json",
    "risk_claims.json",
    "prior_matches.json",
    "team_prior_stats.json",
    "player_prior_stats.json",
    "answer_template.json",
    "public_data_catalog.md",
)

POSITION_MAP = {
    "Goalkeeper": "GK",
    "Defender": "DEF",
    "Midfielder": "MID",
    "Attacker": "FWD",
    "Forward": "FWD",
}

FINISHED_STATUS = {"FT", "AET", "PEN"}
KNOCKOUT_ROUNDS = {"Round of 16", "Quarter-finals", "Semi-finals", "3rd Place Final", "Final"}

CLAIM_TYPES = {
    "match_2plus_goals": {
        "category": "green",
        "required_fields": ["claim_id", "match_id"],
        "description": "The selected match finishes with at least 2 total goals.",
    },
    "no_goal_first_10": {
        "category": "green",
        "required_fields": ["claim_id", "match_id"],
        "description": "No goal is scored from minute 1 through minute 10.",
    },
    "goal_before_halftime": {
        "category": "green",
        "required_fields": ["claim_id", "match_id"],
        "description": "At least one goal is scored before halftime.",
    },
    "match_2plus_cards": {
        "category": "green",
        "required_fields": ["claim_id", "match_id"],
        "description": "The selected match has at least 2 card events.",
    },
    "both_teams_score": {
        "category": "yellow",
        "required_fields": ["claim_id", "match_id"],
        "description": "Both teams score at least once.",
    },
    "match_over_2_5_goals": {
        "category": "yellow",
        "required_fields": ["claim_id", "match_id"],
        "description": "The selected match finishes with 3 or more total goals.",
    },
    "team_scores_first": {
        "category": "yellow",
        "required_fields": ["claim_id", "match_id", "team_id"],
        "description": "The selected team scores the first countable goal.",
    },
    "player_scores": {
        "category": "yellow",
        "required_fields": ["claim_id", "match_id", "player_id"],
        "description": "The selected player scores at least one non-own goal.",
    },
    "exact_score": {
        "category": "red",
        "required_fields": ["claim_id", "match_id", "home_score", "away_score"],
        "description": "The selected match finishes with the submitted home and away score.",
    },
    "player_scores_2plus": {
        "category": "red",
        "required_fields": ["claim_id", "match_id", "player_id"],
        "description": "The selected player scores at least 2 non-own goals.",
    },
    "team_wins_by_3plus": {
        "category": "red",
        "required_fields": ["claim_id", "match_id", "team_id"],
        "description": "The selected team wins by at least 3 goals.",
    },
    "match_goes_to_extra_time": {
        "category": "red",
        "required_fields": ["claim_id", "match_id"],
        "description": "The knockout match reaches extra time.",
        "knockout_only": True,
    },
    "match_goes_to_penalties": {
        "category": "red",
        "required_fields": ["claim_id", "match_id"],
        "description": "The knockout match reaches a penalty shootout.",
        "knockout_only": True,
    },
}


@dataclass(frozen=True)
class PublicDataSnapshot:
    public_data_dir: Path
    schema_path: Path
    files: list[Path]


@dataclass(frozen=True)
class PublicDataBuildResult:
    output_dir: Path
    files: list[Path]
    matchday_id: str
    fixture_count: int
    player_count: int
    prior_match_count: int


class ApiFootballClient:
    def __init__(self, api_key: str | None = None, raw_source_dir: Path = DEFAULT_RAW_SOURCE_DIR):
        self.api_key = api_key or resolve_api_key()
        self.raw_source_dir = raw_source_dir
        self.min_interval_seconds = CONFIG.get_float("api_football", "min_interval_seconds", 7.0)
        self.rate_limit_retries = CONFIG.get_int("api_football", "rate_limit_retries", 5)
        self.rate_limit_sleep_seconds = CONFIG.get_float("api_football", "rate_limit_sleep_seconds", 20.0)
        self._last_request_at = 0.0

    def get(
        self,
        endpoint: str,
        params: dict[str, str | int],
        refresh: bool = False,
        raise_on_errors: bool = True,
    ) -> dict[str, Any]:
        endpoint = endpoint.strip("/")
        cache_path = self._cache_path(endpoint, params)
        if cache_path.is_file() and not refresh:
            cached_payload = json.loads(cache_path.read_text(encoding="utf-8"))
            if not _is_rate_limit_error(cached_payload):
                return cached_payload

        if not self.api_key:
            raise RuntimeError("API-Football key is not configured. Set APISPORTS_KEY or API_FOOTBALL_KEY.")

        query = urlencode({key: value for key, value in params.items() if value is not None})
        path = f"/{endpoint}?{query}" if query else f"/{endpoint}"

        payload: dict[str, Any] = {}
        for attempt in range(self.rate_limit_retries + 1):
            self._wait_for_rate_window()
            payload = self._request_json(path)
            if not _is_rate_limit_error(payload):
                cache_path.parent.mkdir(parents=True, exist_ok=True)
                cache_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
                break
            if attempt < self.rate_limit_retries:
                time.sleep(self.rate_limit_sleep_seconds)

        if payload.get("errors") and raise_on_errors:
            raise RuntimeError(f"API-Football returned errors for {endpoint}: {payload['errors']}")
        return payload

    def get_all_pages(self, endpoint: str, params: dict[str, str | int], refresh: bool = False) -> list[dict[str, Any]]:
        first = self.get(endpoint, {**params, "page": 1}, refresh=refresh)
        responses = list(first.get("response") or [])
        total_pages = int((first.get("paging") or {}).get("total") or 1)
        for page in range(2, total_pages + 1):
            payload = self.get(endpoint, {**params, "page": page}, refresh=refresh, raise_on_errors=False)
            if payload.get("errors"):
                if _is_free_page_limit_error(payload):
                    break
                if _is_rate_limit_error(payload):
                    raise RuntimeError(
                        "API-Football per-minute rate limit is still active after retries. "
                        "Increase api_football.rate_limit_sleep_seconds or api_football.min_interval_seconds."
                    )
                raise RuntimeError(f"API-Football returned errors for {endpoint}: {payload['errors']}")
            responses.extend(payload.get("response") or [])
        return responses

    def _cache_path(self, endpoint: str, params: dict[str, str | int]) -> Path:
        clean_params = {key: params[key] for key in sorted(params) if params[key] is not None}
        digest = hashlib.sha256(json.dumps(clean_params, sort_keys=True).encode("utf-8")).hexdigest()[:16]
        return self.raw_source_dir / f"{endpoint}-{digest}.json"

    def _wait_for_rate_window(self) -> None:
        elapsed = time.monotonic() - self._last_request_at
        wait_seconds = self.min_interval_seconds - elapsed
        if wait_seconds > 0:
            time.sleep(wait_seconds)
        self._last_request_at = time.monotonic()

    def _request_json(self, path: str) -> dict[str, Any]:
        connection = http.client.HTTPSConnection("v3.football.api-sports.io")
        try:
            connection.request("GET", path, headers={"x-apisports-key": self.api_key})
            response = connection.getresponse()
            body = response.read().decode("utf-8")
        finally:
            connection.close()
        return json.loads(body)


def build_public_data(
    as_of_date: date,
    output_dir: Path = DEFAULT_PUBLIC_DATA_DIR,
    league_id: str = DEFAULT_LEAGUE_ID,
    season: str = DEFAULT_SEASON,
    refresh: bool = False,
) -> PublicDataBuildResult:
    """Build the static data bundle available to skill executions for one day."""
    client = ApiFootballClient()
    fixtures = client.get("fixtures", {"league": league_id, "season": season}, refresh=refresh).get("response") or []
    teams_payload = client.get("teams", {"league": league_id, "season": season}, refresh=refresh).get("response") or []

    incoming_fixtures = [fixture for fixture in fixtures if _fixture_date(fixture) == as_of_date]
    players_payload = _fetch_players_for_fixtures(
        client=client,
        incoming_fixtures=incoming_fixtures,
        league_id=league_id,
        season=season,
        refresh=refresh,
    )
    prior_fixtures = [
        fixture
        for fixture in fixtures
        if _fixture_date(fixture) < as_of_date and _fixture_status(fixture) in FINISHED_STATUS
    ]
    prior_fixtures = [_fixture_details(client, fixture, refresh=refresh) for fixture in prior_fixtures]

    matchday_id = f"wc-{season}-{as_of_date.strftime('%Y%m%d')}"
    generated_at = _utc_now()
    matches = [_public_match(fixture) for fixture in incoming_fixtures]
    prior_matches = [_public_prior_match(fixture) for fixture in prior_fixtures]
    team_prior_stats = _build_team_prior_stats(prior_fixtures)
    player_prior_stats = _build_player_prior_stats(prior_fixtures)
    teams = _build_teams(teams_payload, incoming_fixtures, team_prior_stats)
    players = _build_players(players_payload, incoming_fixtures, player_prior_stats)
    risk_claims = _build_risk_claims(matchday_id, incoming_fixtures)

    payloads: dict[str, dict[str, Any] | list[dict[str, Any]] | str] = {
        "manifest.json": _build_manifest(generated_at, matchday_id, as_of_date, league_id, season),
        "matchday.json": _build_matchday(generated_at, matchday_id, as_of_date, league_id, season, matches),
        "matches.json": matches,
        "teams.json": teams,
        "players.json": players,
        "risk_claims.json": risk_claims,
        "prior_matches.json": prior_matches,
        "team_prior_stats.json": sorted(team_prior_stats.values(), key=lambda item: item["team_name"]),
        "player_prior_stats.json": sorted(player_prior_stats.values(), key=lambda item: item["player_name"]),
        "answer_template.json": _build_answer_template(matchday_id),
        "public_data_catalog.md": _build_catalog(matchday_id, matches, prior_matches, teams, players, risk_claims),
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    archive_dir = output_dir / "by_date" / as_of_date.isoformat()
    archive_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for filename, payload in payloads.items():
        path = output_dir / filename
        _write_public_payload(path, payload)
        _write_public_payload(archive_dir / filename, payload)
        written.append(path)

    index_payload = _update_matchdays_index(
        output_dir=output_dir,
        generated_at=generated_at,
        matchday_id=matchday_id,
        match_date=as_of_date,
        league_id=league_id,
        season=season,
        fixture_ids=[match["id"] for match in matches],
        archive_dir=archive_dir,
        fixture_count=len(matches),
        prior_match_count=len(prior_matches),
    )
    _write_public_payload(output_dir / "matchdays_index.json", index_payload)
    _write_public_payload(archive_dir / "matchdays_index.json", index_payload)
    written.append(output_dir / "matchdays_index.json")

    return PublicDataBuildResult(
        output_dir=output_dir,
        files=written,
        matchday_id=matchday_id,
        fixture_count=len(matches),
        player_count=len(players),
        prior_match_count=len(prior_matches),
    )


def create_public_data_snapshot(run_dir: Path, source_public_data_dir: Path, source_schema_path: Path) -> PublicDataSnapshot:
    """Copy the generated public-data artifact bundle into the immutable run folder."""
    if not source_public_data_dir.is_dir():
        raise FileNotFoundError(f"Public data directory does not exist: {source_public_data_dir}")
    if not source_schema_path.is_file():
        raise FileNotFoundError(f"Submission schema does not exist: {source_schema_path}")

    public_data_dir = run_dir / "public_data"
    schema_dir = run_dir / "schemas"
    schema_path = schema_dir / "team_submission.schema.json"
    public_data_dir.mkdir(parents=True, exist_ok=True)
    schema_dir.mkdir(parents=True, exist_ok=True)

    copied_files: list[Path] = []
    for filename in PUBLIC_DATA_FILES:
        source_path = source_public_data_dir / filename
        if not source_path.is_file():
            raise FileNotFoundError(f"Public data file does not exist: {source_path}")
        destination_path = public_data_dir / filename
        shutil.copy2(source_path, destination_path)
        copied_files.append(destination_path)

    shutil.copy2(source_schema_path, schema_path)
    return PublicDataSnapshot(public_data_dir=public_data_dir, schema_path=schema_path, files=[*copied_files, schema_path])


def _fetch_players_for_fixtures(
    *,
    client: ApiFootballClient,
    incoming_fixtures: list[dict[str, Any]],
    league_id: str,
    season: str,
    refresh: bool,
) -> list[dict[str, Any]]:
    """Temporary free-plan-friendly player discovery.

    API-Football free plans cap the broad ``players`` endpoint at page 3.
    Fetching only the teams in the active matchday keeps the public bundle
    useful without changing the data shape consumed by the rest of the app.
    """
    team_ids = sorted(
        {
            str((fixture.get("teams") or {}).get(side, {}).get("id"))
            for fixture in incoming_fixtures
            for side in ("home", "away")
            if (fixture.get("teams") or {}).get(side, {}).get("id") is not None
        }
    )
    players_by_team_and_id: dict[str, dict[str, Any]] = {}
    for team_id in team_ids:
        team_players = client.get_all_pages(
            "players",
            {"league": league_id, "season": season, "team": team_id},
            refresh=refresh,
        )
        for item in team_players:
            player = item.get("player") or {}
            player_id = player.get("id")
            if player_id is None:
                continue
            players_by_team_and_id[f"{team_id}:{player_id}"] = item
    return list(players_by_team_and_id.values())


def _is_free_page_limit_error(payload: dict[str, Any]) -> bool:
    message = _error_message(payload)
    return "free plans are limited" in message and "page" in message


def _is_rate_limit_error(payload: dict[str, Any]) -> bool:
    message = _error_message(payload)
    return "ratelimit" in message or "per-minute request limit" in message or "too many requests" in message


def _error_message(payload: dict[str, Any]) -> str:
    errors = payload.get("errors") or {}
    if isinstance(errors, dict):
        message = " ".join(str(value) for value in errors.values())
    else:
        message = str(errors)
    return message.lower()


def _write_public_payload(path: Path, payload: dict[str, Any] | list[dict[str, Any]] | str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(payload, str):
        path.write_text(payload, encoding="utf-8")
        return
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _update_matchdays_index(
    *,
    output_dir: Path,
    generated_at: str,
    matchday_id: str,
    match_date: date,
    league_id: str,
    season: str,
    fixture_ids: list[str],
    archive_dir: Path,
    fixture_count: int,
    prior_match_count: int,
) -> dict[str, Any]:
    index_path = output_dir / "matchdays_index.json"
    existing_entries: list[dict[str, Any]] = []
    if index_path.is_file():
        try:
            existing = json.loads(index_path.read_text(encoding="utf-8"))
            existing_entries = list(existing.get("matchdays") or [])
        except json.JSONDecodeError:
            existing_entries = []

    new_entry = {
        "matchday_id": matchday_id,
        "match_date": match_date.isoformat(),
        "generated_at": generated_at,
        "provider": "api-football",
        "league_id": league_id,
        "season": season,
        "fixture_ids": fixture_ids,
        "fixture_count": fixture_count,
        "prior_match_count": prior_match_count,
        "archive_path": str(archive_dir),
    }
    entries = [
        entry
        for entry in existing_entries
        if entry.get("match_date") != match_date.isoformat() and entry.get("matchday_id") != matchday_id
    ]
    entries.append(new_entry)
    entries.sort(key=lambda item: item.get("match_date") or "")
    return {
        "schema_version": "fantasy-cup-public-matchday-index-v1",
        "updated_at": generated_at,
        "matchdays": entries,
    }


def resolve_api_key() -> str:
    _load_env_file(BACKEND_ROOT / ".env")
    _load_env_file(INNO_ROOT / ".env")
    return os.getenv("APISPORTS_KEY", "").strip() or os.getenv("API_FOOTBALL_KEY", "").strip()


def _load_env_file(path: Path) -> None:
    if not path.is_file():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _fixture_details(client: ApiFootballClient, fixture: dict[str, Any], refresh: bool = False) -> dict[str, Any]:
    fixture_id = str(fixture["fixture"]["id"])
    payload = client.get("fixtures", {"id": fixture_id}, refresh=refresh)
    response = payload.get("response") or []
    return response[0] if response else fixture


def _fixture_date(fixture: dict[str, Any]) -> date:
    raw_date = fixture["fixture"]["date"].replace("Z", "+00:00")
    return datetime.fromisoformat(raw_date).date()


def _fixture_status(fixture: dict[str, Any]) -> str:
    return str(((fixture.get("fixture") or {}).get("status") or {}).get("short") or "")


def _public_match(fixture: dict[str, Any]) -> dict[str, Any]:
    fixture_data = fixture["fixture"]
    league = fixture.get("league") or {}
    teams = fixture.get("teams") or {}
    return {
        "id": str(fixture_data["id"]),
        "provider": "api-football",
        "provider_fixture_id": str(fixture_data["id"]),
        "round": league.get("round"),
        "stage": _stage_from_round(league.get("round")),
        "kickoff": fixture_data.get("date"),
        "venue": fixture_data.get("venue") or {},
        "home_team": _team_ref(teams.get("home") or {}),
        "away_team": _team_ref(teams.get("away") or {}),
    }


def _public_prior_match(fixture: dict[str, Any]) -> dict[str, Any]:
    match = _public_match(fixture)
    goals = fixture.get("goals") or {}
    score = fixture.get("score") or {}
    events = fixture.get("events") or []
    match.update(
        {
            "status": (fixture.get("fixture") or {}).get("status") or {},
            "score": {
                "home": goals.get("home"),
                "away": goals.get("away"),
                "halftime": score.get("halftime"),
                "fulltime": score.get("fulltime"),
                "extratime": score.get("extratime"),
                "penalty": score.get("penalty"),
            },
            "event_counts": _event_counts(events),
        }
    )
    return match


def _team_ref(team: dict[str, Any]) -> dict[str, str | None]:
    return {
        "id": str(team.get("id")) if team.get("id") is not None else None,
        "name": team.get("name"),
        "logo": team.get("logo"),
    }


def _build_teams(
    teams_payload: list[dict[str, Any]],
    incoming_fixtures: list[dict[str, Any]],
    prior_stats: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    incoming_team_ids = {
        str((fixture.get("teams") or {}).get(side, {}).get("id"))
        for fixture in incoming_fixtures
        for side in ("home", "away")
        if (fixture.get("teams") or {}).get(side, {}).get("id") is not None
    }
    teams_by_id: dict[str, dict[str, Any]] = {}

    for item in teams_payload:
        team = item.get("team") or {}
        team_id = str(team.get("id"))
        if team_id not in incoming_team_ids:
            continue
        teams_by_id[team_id] = {
            "id": team_id,
            "name": team.get("name"),
            "code": team.get("code"),
            "country": team.get("country"),
            "logo": team.get("logo"),
            "incoming_matches": [],
            "prior_stats": prior_stats.get(team_id, _empty_team_stats(team_id, team.get("name"))),
        }

    for fixture in incoming_fixtures:
        match_id = str(fixture["fixture"]["id"])
        home = fixture["teams"]["home"]
        away = fixture["teams"]["away"]
        for side, opponent in (("home", away), ("away", home)):
            team = fixture["teams"][side]
            team_id = str(team["id"])
            entry = teams_by_id.setdefault(
                team_id,
                {
                    "id": team_id,
                    "name": team.get("name"),
                    "code": None,
                    "country": None,
                    "logo": team.get("logo"),
                    "incoming_matches": [],
                    "prior_stats": prior_stats.get(team_id, _empty_team_stats(team_id, team.get("name"))),
                },
            )
            entry["incoming_matches"].append(
                {
                    "match_id": match_id,
                    "side": side,
                    "opponent_team_id": str(opponent.get("id")),
                    "opponent": opponent.get("name"),
                }
            )

    return sorted(teams_by_id.values(), key=lambda item: item.get("name") or item["id"])


def _build_players(
    players_payload: list[dict[str, Any]],
    incoming_fixtures: list[dict[str, Any]],
    prior_stats: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    team_matches: dict[str, list[str]] = {}
    team_names: dict[str, str] = {}
    for fixture in incoming_fixtures:
        match_id = str(fixture["fixture"]["id"])
        for side in ("home", "away"):
            team = fixture["teams"][side]
            team_id = str(team["id"])
            team_matches.setdefault(team_id, []).append(match_id)
            team_names[team_id] = team.get("name")

    players: list[dict[str, Any]] = []
    for item in players_payload:
        player = item.get("player") or {}
        statistics = item.get("statistics") or []
        for stat in statistics:
            team = stat.get("team") or {}
            team_id = str(team.get("id"))
            if team_id not in team_matches:
                continue
            player_id = str(player.get("id"))
            position = _normalize_position(((stat.get("games") or {}).get("position")))
            for match_id in team_matches[team_id]:
                player_stats = prior_stats.get(player_id, _empty_player_stats(player_id, player.get("name"), team_id, team.get("name") or team_names.get(team_id)))
                players.append(
                    {
                        "record_id": f"{match_id}:{player_id}",
                        "match_id": match_id,
                        "player_id": player_id,
                        "name": player.get("name"),
                        "team_id": team_id,
                        "team": team.get("name") or team_names.get(team_id),
                        "position": position,
                        "photo": player.get("photo"),
                        "prior_stats": player_stats,
                    }
                )

    deduped = {player["record_id"]: player for player in players}
    return sorted(deduped.values(), key=lambda item: (item["match_id"], item["team"] or "", item["name"] or ""))


def _build_risk_claims(matchday_id: str, incoming_fixtures: list[dict[str, Any]]) -> dict[str, Any]:
    claim_types = [
        {
            "claim_id": claim_id,
            "category": config["category"],
            "required_fields": config["required_fields"],
            "description": config["description"],
        }
        for claim_id, config in sorted(CLAIM_TYPES.items())
    ]
    available_claims: list[dict[str, Any]] = []

    for fixture in incoming_fixtures:
        match = _public_match(fixture)
        match_id = match["id"]
        match_label = f"{match['home_team']['name']} vs {match['away_team']['name']}"
        team_options = [match["home_team"], match["away_team"]]
        is_knockout = match["stage"] == "knockout"

        for claim_id, config in sorted(CLAIM_TYPES.items()):
            if config.get("knockout_only") and not is_knockout:
                continue
            claim = {
                "claim_key": f"{match_id}:{claim_id}",
                "claim_id": claim_id,
                "match_id": match_id,
                "match_label": match_label,
                "category": config["category"],
                "required_fields": config["required_fields"],
                "description": config["description"],
                "parameters": {"match_id": match_id},
            }
            if "team_id" in config["required_fields"]:
                claim["parameter_options"] = {"team_id": team_options}
            if "player_id" in config["required_fields"]:
                claim["parameter_options"] = {"player_id": {"source_file": "players.json", "filter": {"match_id": match_id}}}
            if "home_score" in config["required_fields"]:
                claim["parameter_options"] = {"home_score": "non-negative integer", "away_score": "non-negative integer"}
            available_claims.append(claim)

    return {
        "schema_version": "fantasy-cup-public-context-v1",
        "matchday_id": matchday_id,
        "claim_types": claim_types,
        "available_claims": available_claims,
        "stake_rules": {
            "green": "15% of the team's points before the matchday",
            "yellow": "25% of the team's points before the matchday",
            "red": "35% of the team's points before the matchday",
        },
    }


def _build_team_prior_stats(prior_fixtures: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    stats: dict[str, dict[str, Any]] = {}
    for fixture in prior_fixtures:
        goals = fixture.get("goals") or {}
        home_goals = int(goals.get("home") or 0)
        away_goals = int(goals.get("away") or 0)
        home = fixture["teams"]["home"]
        away = fixture["teams"]["away"]
        _apply_team_result(stats, str(home["id"]), home.get("name"), home_goals, away_goals)
        _apply_team_result(stats, str(away["id"]), away.get("name"), away_goals, home_goals)
    return stats


def _apply_team_result(stats: dict[str, dict[str, Any]], team_id: str, name: str | None, goals_for: int, goals_against: int) -> None:
    entry = stats.setdefault(team_id, _empty_team_stats(team_id, name))
    entry["played"] += 1
    entry["goals_for"] += goals_for
    entry["goals_against"] += goals_against
    if goals_for > goals_against:
        entry["wins"] += 1
    elif goals_for < goals_against:
        entry["losses"] += 1
    else:
        entry["draws"] += 1


def _build_player_prior_stats(prior_fixtures: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    stats: dict[str, dict[str, Any]] = {}
    for fixture in prior_fixtures:
        for event in fixture.get("events") or []:
            player = event.get("player") or {}
            team = event.get("team") or {}
            player_id = player.get("id")
            if player_id is None:
                continue
            entry = stats.setdefault(
                str(player_id),
                _empty_player_stats(str(player_id), player.get("name"), str(team.get("id")), team.get("name")),
            )
            event_type = event.get("type")
            detail = event.get("detail")
            if event_type == "Goal" and detail == "Own Goal":
                entry["own_goals"] += 1
            elif event_type == "Goal":
                entry["goals"] += 1
            elif event_type == "Card" and detail == "Yellow Card":
                entry["yellow_cards"] += 1
            elif event_type == "Card":
                entry["red_cards"] += 1
            assist = event.get("assist") or {}
            assist_id = assist.get("id")
            if assist_id is not None:
                assist_entry = stats.setdefault(
                    str(assist_id),
                    _empty_player_stats(str(assist_id), assist.get("name"), str(team.get("id")), team.get("name")),
                )
                assist_entry["assists"] += 1
    return stats


def _event_counts(events: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"goals": 0, "own_goals": 0, "yellow_cards": 0, "red_cards": 0}
    for event in events:
        if event.get("type") == "Goal" and event.get("detail") == "Own Goal":
            counts["own_goals"] += 1
        elif event.get("type") == "Goal":
            counts["goals"] += 1
        elif event.get("type") == "Card" and event.get("detail") == "Yellow Card":
            counts["yellow_cards"] += 1
        elif event.get("type") == "Card":
            counts["red_cards"] += 1
    return counts


def _build_manifest(generated_at: str, matchday_id: str, match_date: date, league_id: str, season: str) -> dict[str, Any]:
    return {
        "schema_version": "fantasy-cup-public-context-v1",
        "generated_at": generated_at,
        "matchday_id": matchday_id,
        "match_date": match_date.isoformat(),
        "source": {
            "provider": "api-football",
            "league_id": league_id,
            "season": season,
            "source_mode": "simulated-world-cup-as-live",
        },
        "files": {filename.removesuffix(".json").replace("_", "-"): filename for filename in PUBLIC_DATA_FILES},
        "redaction": "Incoming fixture results, events, and scoring truth are omitted until the next daily generation.",
    }


def _build_matchday(
    generated_at: str,
    matchday_id: str,
    match_date: date,
    league_id: str,
    season: str,
    matches: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "schema_version": "fantasy-cup-public-context-v1",
        "generated_at": generated_at,
        "matchday_id": matchday_id,
        "match_date": match_date.isoformat(),
        "competition": {"provider": "api-football", "league_id": league_id, "season": season},
        "fixture_ids": [match["id"] for match in matches],
        "public_run_mode": "World Cup simulated as pre-match context",
        "fantasy_xi_rules": {
            "selection_count": 11,
            "selection_id": "Use players[].record_id from players.json.",
            "positions": {
                "GK": {"min": 1, "max": 1, "label": "Goalkeeper"},
                "DEF": {"min": 3, "max": 5, "label": "Defender"},
                "MID": {"min": 3, "max": 5, "label": "Midfielder"},
                "FWD": {"min": 1, "max": 3, "label": "Forward"},
            },
        },
        "risk_play_rules": {"optional": True, "select_at_most": 1, "claim_source": "risk_claims.json"},
        "hidden_until_scoring": [
            "incoming fixture status and final score",
            "incoming fixture event timeline",
            "incoming player minutes, goals, assists, cards, saves, own goals, and clean-sheet truth",
            "risk claim outcomes and scoring evidence",
        ],
    }


def _build_answer_template(matchday_id: str) -> dict[str, Any]:
    return {
        "team_id": "replace-with-team-id",
        "team_name": "Replace With Team Name",
        "matchday_id": matchday_id,
        "answers": {
            "fantasy_xi": [{"record_id": f"replace-with-record-id-{index}"} for index in range(1, 12)],
            "risk_play": None,
            "strategy_summary": "One short paragraph explaining the picks.",
        },
    }


def _build_catalog(
    matchday_id: str,
    matches: list[dict[str, Any]],
    prior_matches: list[dict[str, Any]],
    teams: list[dict[str, Any]],
    players: list[dict[str, Any]],
    risk_claims: dict[str, Any],
) -> str:
    lines = [
        "# Public Data Catalog",
        "",
        f"Matchday ID: `{matchday_id}`",
        "",
        "## Files",
        "",
        "- `matchday.json`: rules, fixture IDs, and hidden-data policy.",
        "- `matches.json`: incoming fixtures available for this simulated matchday.",
        "- `teams.json`: incoming teams and their prior public stats.",
        "- `players.json`: eligible player records; submit `record_id` values in Fantasy XI.",
        "- `risk_claims.json`: allowed Risk Play claim types and match-specific claim options.",
        "- `prior_matches.json`: public results from matches before this simulated day.",
        "- `team_prior_stats.json`: team form derived from prior public matches.",
        "- `player_prior_stats.json`: event-derived player history from prior public matches.",
        "- `answer_template.json`: minimal single-team answer shape.",
        "",
        "## Incoming Fixtures",
        "",
    ]
    if matches:
        for match in matches:
            lines.append(f"- `{match['id']}`: {match['home_team']['name']} vs {match['away_team']['name']} ({match['kickoff']})")
    else:
        lines.append("- No incoming fixtures for this generated day.")

    lines.extend(["", "## Prior Public Results", ""])
    if prior_matches:
        for match in prior_matches:
            score = match["score"]
            lines.append(f"- `{match['id']}`: {match['home_team']['name']} {score['home']}-{score['away']} {match['away_team']['name']}")
    else:
        lines.append("- No prior matches are public yet.")

    lines.extend(
        [
            "",
            "## Inventory",
            "",
            f"- Teams in scope: {len(teams)}",
            f"- Eligible player records: {len(players)}",
            f"- Risk claim options: {len(risk_claims['available_claims'])}",
            "",
        ]
    )
    return "\n".join(lines) + "\n"


def _empty_team_stats(team_id: str, name: str | None) -> dict[str, Any]:
    return {
        "team_id": team_id,
        "team_name": name,
        "played": 0,
        "wins": 0,
        "draws": 0,
        "losses": 0,
        "goals_for": 0,
        "goals_against": 0,
    }


def _empty_player_stats(player_id: str, name: str | None, team_id: str | None, team_name: str | None) -> dict[str, Any]:
    return {
        "player_id": player_id,
        "player_name": name,
        "team_id": team_id,
        "team_name": team_name,
        "goals": 0,
        "assists": 0,
        "own_goals": 0,
        "yellow_cards": 0,
        "red_cards": 0,
    }


def _normalize_position(position: str | None) -> str | None:
    return POSITION_MAP.get(position or "", position)


def _stage_from_round(round_name: str | None) -> str:
    if round_name in KNOCKOUT_ROUNDS:
        return "knockout"
    return "group"


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate public Fantasy Cup data for one simulated World Cup day.")
    parser.add_argument("--as-of-date", required=True, help="Simulated morning date in YYYY-MM-DD format, e.g. 2022-11-20.")
    parser.add_argument("--league-id", default=DEFAULT_LEAGUE_ID)
    parser.add_argument("--season", default=DEFAULT_SEASON)
    parser.add_argument("--out", type=Path, default=DEFAULT_PUBLIC_DATA_DIR)
    parser.add_argument("--refresh", action="store_true", help="Ignore raw response cache and call API-Football again.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = build_public_data(
        as_of_date=date.fromisoformat(args.as_of_date),
        output_dir=args.out,
        league_id=str(args.league_id),
        season=str(args.season),
        refresh=args.refresh,
    )
    print(f"Public data written: {result.output_dir}")
    print(f"Matchday: {result.matchday_id}")
    print(f"Incoming fixtures: {result.fixture_count}")
    print(f"Eligible player records: {result.player_count}")
    print(f"Prior public matches: {result.prior_match_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
