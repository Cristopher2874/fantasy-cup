"""Generate source-of-truth scoring data after matches finish.

This module is standalone inside ``inno-fantasy``. It calls API-Football for
the same simulated World Cup matchday used by public data, normalizes the
real fixture results, and writes the truth bundle consumed by the scoring step.
"""
from __future__ import annotations

import argparse
import json
import shutil
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from services.data_generator.public_data import (
    ApiFootballClient,
    DATA_ROOT,
    DEFAULT_LEAGUE_ID,
    DEFAULT_PUBLIC_DATA_DIR,
    DEFAULT_SEASON,
    FINISHED_STATUS,
)


DEFAULT_TRUTH_DIR = DATA_ROOT / "source_of_truth"
DEFAULT_RAW_TRUTH_SOURCE_DIR = DATA_ROOT / "source" / "api-football-truth"
TIMEZONE = "UTC"

SOURCE_TRUTH_FILES = (
    "latest_truth.json",
    "source_truth_catalog.md",
)

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
        "source": "fixture final goals",
    },
    "no_goal_first_10": {
        "category": "green",
        "required_fields": ["match_id"],
        "source": "goal events with elapsed minute",
    },
    "goal_before_halftime": {
        "category": "green",
        "required_fields": ["match_id"],
        "source": "goal events with first-half timing",
    },
    "match_2plus_cards": {
        "category": "green",
        "required_fields": ["match_id"],
        "source": "card events",
    },
    "both_teams_score": {
        "category": "yellow",
        "required_fields": ["match_id"],
        "source": "fixture final goals",
    },
    "match_over_2_5_goals": {
        "category": "yellow",
        "required_fields": ["match_id"],
        "source": "fixture final goals",
    },
    "team_scores_first": {
        "category": "yellow",
        "required_fields": ["match_id", "team_id"],
        "source": "first credited non-shootout goal event",
    },
    "player_scores": {
        "category": "yellow",
        "required_fields": ["match_id", "player_id"],
        "source": "non-own, non-shootout goal events",
    },
    "exact_score": {
        "category": "red",
        "required_fields": ["match_id", "home_score", "away_score"],
        "source": "fixture final goals, excluding shootout score",
    },
    "player_scores_2plus": {
        "category": "red",
        "required_fields": ["match_id", "player_id"],
        "source": "non-own, non-shootout goal events",
    },
    "team_wins_by_3plus": {
        "category": "red",
        "required_fields": ["match_id", "team_id"],
        "source": "fixture final goals, excluding shootout score",
    },
    "match_goes_to_extra_time": {
        "category": "red",
        "required_fields": ["match_id"],
        "source": "fixture status and extra-time score fields",
    },
    "match_goes_to_penalties": {
        "category": "red",
        "required_fields": ["match_id"],
        "source": "fixture status and penalty score fields",
    },
}

FANTASY_SCORING_CAPABILITIES = {
    "starts": "Derived from player match statistics games.substitute and minutes.",
    "plays_60": "Derived from player match statistics games.minutes.",
    "goal": "Read from player match statistics goals.total.",
    "assist": "Read from player match statistics goals.assists.",
    "clean_sheet": "Derived from final goals conceded plus player position/minutes.",
    "goalkeeper_saves": "Read from player match statistics goals.saves.",
    "yellow_card": "Read from player match statistics cards.yellow.",
    "red_card": "Read from player match statistics cards.red.",
    "own_goal": "Derived from fixture events detail=Own Goal.",
}


@dataclass(frozen=True)
class SourceTruthBuildResult:
    output_dir: Path
    latest_truth_path: Path
    final_truth_path: Path
    raw_path: Path
    catalog_path: Path
    matchday_id: str
    fixture_count: int
    player_count: int
    incomplete_fixture_ids: list[str]


@dataclass(frozen=True)
class SourceTruthSnapshot:
    truth_dir: Path
    files: list[Path]


class FootballTruthParser:
    def __init__(
        self,
        *,
        matchday_id: str,
        league_id: str,
        season: str,
        source_mode: str,
        match_date: date,
        fixture_ids: list[str],
        incomplete_fixture_ids: list[str],
    ) -> None:
        self.matchday_id = matchday_id
        self.league_id = league_id
        self.season = season
        self.source_mode = source_mode
        self.match_date = match_date
        self.fixture_ids = fixture_ids
        self.incomplete_fixture_ids = incomplete_fixture_ids

    def normalize(self, fixtures: list[dict[str, Any]], generated_at: str) -> dict[str, Any]:
        matches = []
        player_records = []

        for fixture in fixtures:
            match, players = self.parse_match(fixture)
            matches.append(match)
            for player in players.values():
                player["record_id"] = f"{player['match_id']}:{player['id']}"
                player_records.append(player)

        matches.sort(key=lambda item: item.get("kickoff") or "")
        player_records.sort(key=lambda item: (item["match_id"], item["team"] or "", item["name"] or ""))
        return {
            "schema_version": "fantasy-cup-truth-v1",
            "generated_at": generated_at,
            "matchday_id": self.matchday_id,
            "match_date": self.match_date.isoformat(),
            "source": {
                "provider": "api-football",
                "league_id": self.league_id,
                "season": self.season,
                "source_mode": self.source_mode,
                "timezone": TIMEZONE,
                "fixture_ids": self.fixture_ids,
            },
            "state": {
                "complete": not self.incomplete_fixture_ids,
                "incomplete_fixture_ids": self.incomplete_fixture_ids,
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
                ],
            },
            "point_rules": POINT_RULES,
            "matches": matches,
            "players": player_records,
            "scoring_inputs": {
                "player_points_by_record_id": {
                    player["record_id"]: player["fantasy_points"] for player in player_records
                },
                "risk_truth_by_match_id": {match["id"]: match["risk_truth"] for match in matches},
            },
        }

    def parse_match(self, fixture: dict[str, Any]) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
        home = fixture["teams"]["home"]
        away = fixture["teams"]["away"]
        home_goals, away_goals = self.final_goals(fixture)
        players = self.parse_players(fixture)
        match = {
            "id": str(fixture["fixture"]["id"]),
            "provider": "api-football",
            "provider_fixture_id": str(fixture["fixture"]["id"]),
            "round": (fixture.get("league") or {}).get("round"),
            "stage": self.stage_from_round((fixture.get("league") or {}).get("round")),
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
                "fulltime": (fixture.get("score") or {}).get("fulltime"),
                "extratime": (fixture.get("score") or {}).get("extratime"),
                "penalty": (fixture.get("score") or {}).get("penalty"),
                "winner_team_id": self.winner_team_id(fixture),
                "went_to_extra_time": self.went_to_extra_time(fixture),
                "went_to_penalties": self.went_to_penalties(fixture),
            },
            "api_data_presence": {
                "events": bool(fixture.get("events")),
                "lineups": bool(fixture.get("lineups")),
                "fixture_statistics": bool(fixture.get("statistics")),
                "player_statistics": bool(fixture.get("players")),
            },
            "risk_truth": self.parse_risk_truth(fixture),
        }
        return match, players

    def parse_players(self, fixture: dict[str, Any]) -> dict[str, dict[str, Any]]:
        own_goals_by_player: dict[str, int] = {}
        for event in fixture.get("events", []) or []:
            if self.is_own_goal(event):
                player_id = str((event.get("player") or {}).get("id") or "")
                if player_id:
                    own_goals_by_player[player_id] = own_goals_by_player.get(player_id, 0) + 1

        players: dict[str, dict[str, Any]] = {}
        for team_block in fixture.get("players", []) or []:
            team = team_block.get("team") or {}
            team_id = str(team.get("id"))
            for player_block in team_block.get("players", []) or []:
                player = player_block.get("player") or {}
                stats = (player_block.get("statistics") or [{}])[0] or {}
                games = stats.get("games") or {}
                goals = stats.get("goals") or {}
                cards = stats.get("cards") or {}
                position = self.normalize_position(games.get("position"))
                minutes = self.int_value(games.get("minutes"))
                starts = bool(minutes and games.get("substitute") is False)
                clean_sheet = bool(
                    position in {"GK", "DEF"}
                    and minutes >= 60
                    and self.team_goals_conceded(fixture, team_id) == 0
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
                        "goals": self.int_value(goals.get("total")),
                        "assists": self.int_value(goals.get("assists")),
                        "clean_sheet": clean_sheet,
                        "saves": self.int_value(goals.get("saves")),
                        "yellow_cards": self.int_value(cards.get("yellow")),
                        "red_cards": self.int_value(cards.get("red")),
                        "own_goals": own_goals_by_player.get(player_id, 0),
                    },
                }
                points, breakdown = self.score_player(truth)
                truth["fantasy_points"] = points
                truth["fantasy_breakdown"] = breakdown
                players[player_id] = truth
        return players

    def parse_risk_truth(self, fixture: dict[str, Any]) -> dict[str, Any]:
        home = fixture["teams"]["home"]
        away = fixture["teams"]["away"]
        home_id = str(home["id"])
        away_id = str(away["id"])
        home_goals, away_goals = self.final_goals(fixture)
        total_goals = home_goals + away_goals
        countable_goals = self.countable_goal_events(fixture)
        non_own_goals = [event for event in countable_goals if not self.is_own_goal(event)]
        card_events = [event for event in fixture.get("events", []) or [] if self.is_card_event(event)]
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

        team_truth = {}
        for team_id in [home_id, away_id]:
            team_truth[team_id] = {
                "scores_first": first_goal_team_id == team_id,
                "wins_by_3plus": team_goal_diff[team_id] >= 3,
                "is_winner": self.winner_team_id(fixture) == team_id,
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

        goal_in_first_10 = any(
            1 <= self.int_value((event.get("time") or {}).get("elapsed")) <= 10 for event in countable_goals
        )
        goal_before_halftime = any(
            self.int_value((event.get("time") or {}).get("elapsed")) <= 45 for event in countable_goals
        )

        return {
            "match_claims": {
                "match_2plus_goals": total_goals >= 2,
                "no_goal_first_10": not goal_in_first_10,
                "goal_before_halftime": goal_before_halftime,
                "match_2plus_cards": len(card_events) >= 2,
                "both_teams_score": home_goals >= 1 and away_goals >= 1,
                "match_over_2_5_goals": total_goals >= 3,
                "match_goes_to_extra_time": self.went_to_extra_time(fixture),
                "match_goes_to_penalties": self.went_to_penalties(fixture),
            },
            "parameterized_claims": {
                "exact_score": {"home_score": home_goals, "away_score": away_goals},
                "team_scores_first": {team_id: value["scores_first"] for team_id, value in team_truth.items()},
                "team_wins_by_3plus": {team_id: value["wins_by_3plus"] for team_id, value in team_truth.items()},
                "player_scores": {player_id: value["scores"] for player_id, value in player_truth.items()},
                "player_scores_2plus": {player_id: value["scores_2plus"] for player_id, value in player_truth.items()},
            },
            "evidence": {
                "total_goals": total_goals,
                "countable_goal_events": len(countable_goals),
                "card_events": len(card_events),
                "first_goal": self.summarize_event(first_goal) if first_goal else None,
                "team_truth": team_truth,
                "player_goal_counts": player_goal_counts,
            },
        }

    def score_player(self, player_truth: dict[str, Any]) -> tuple[int, list[dict[str, Any]]]:
        points = 0
        breakdown = []

        def add(label: str, value: int) -> None:
            nonlocal points
            if value:
                points += value
                breakdown.append({"label": label, "points": value})

        events = player_truth["events"]
        add("Started", POINT_RULES["starts"] if events["starts"] else 0)
        add("Played 60+ minutes", POINT_RULES["plays_60"] if events["minutes"] >= 60 else 0)
        add("Goals", events["goals"] * POINT_RULES["goal"])
        add("Assists", events["assists"] * POINT_RULES["assist"])
        add("Clean sheet", POINT_RULES["clean_sheet"] if events["clean_sheet"] else 0)
        add("Goalkeeper 3+ saves", POINT_RULES["goalkeeper_saves"] if events["saves"] >= 3 else 0)
        add("Yellow cards", events["yellow_cards"] * POINT_RULES["yellow_card"])
        add("Red cards", events["red_cards"] * POINT_RULES["red_card"])
        add("Own goals", events["own_goals"] * POINT_RULES["own_goal"])
        return points, breakdown

    def final_goals(self, fixture: dict[str, Any]) -> tuple[int, int]:
        goals = fixture.get("goals") or {}
        return self.int_value(goals.get("home")), self.int_value(goals.get("away"))

    def team_goals_conceded(self, fixture: dict[str, Any], team_id: str) -> int:
        home_id = str(fixture["teams"]["home"]["id"])
        goals = fixture.get("goals") or {}
        if team_id == home_id:
            return self.int_value(goals.get("away"))
        return self.int_value(goals.get("home"))

    def winner_team_id(self, fixture: dict[str, Any]) -> str | None:
        home_goals, away_goals = self.final_goals(fixture)
        home = fixture["teams"]["home"]
        away = fixture["teams"]["away"]
        if home_goals > away_goals:
            return str(home["id"])
        if away_goals > home_goals:
            return str(away["id"])

        penalty = (fixture.get("score") or {}).get("penalty") or {}
        home_penalties = penalty.get("home")
        away_penalties = penalty.get("away")
        if home_penalties is None or away_penalties is None:
            return None
        if home_penalties > away_penalties:
            return str(home["id"])
        if away_penalties > home_penalties:
            return str(away["id"])
        return None

    def went_to_extra_time(self, fixture: dict[str, Any]) -> bool:
        status = str((fixture.get("fixture") or {}).get("status", {}).get("short", "")).upper()
        extratime = (fixture.get("score") or {}).get("extratime") or {}
        return status in {"AET", "PEN"} or extratime.get("home") is not None or extratime.get("away") is not None

    def went_to_penalties(self, fixture: dict[str, Any]) -> bool:
        status = str((fixture.get("fixture") or {}).get("status", {}).get("short", "")).upper()
        penalty = (fixture.get("score") or {}).get("penalty") or {}
        return status == "PEN" or penalty.get("home") is not None or penalty.get("away") is not None

    def countable_goal_events(self, fixture: dict[str, Any]) -> list[dict[str, Any]]:
        return [
            event
            for event in fixture.get("events", []) or []
            if self.is_goal_event(event) and not self.is_penalty_shootout_goal(event, fixture)
        ]

    def summarize_event(self, event: dict[str, Any]) -> dict[str, Any]:
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

    @staticmethod
    def stage_from_round(round_name: str | None) -> str:
        if not round_name or str(round_name).startswith("Group Stage"):
            return "group"
        return "knockout"

    @staticmethod
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

    @staticmethod
    def int_value(value: Any) -> int:
        return int(value or 0)

    @staticmethod
    def is_card_event(event: dict[str, Any]) -> bool:
        return str(event.get("type", "")).lower() == "card"

    @staticmethod
    def is_goal_event(event: dict[str, Any]) -> bool:
        detail = str(event.get("detail", "")).lower()
        return str(event.get("type", "")).lower() == "goal" and detail != "missed penalty"

    @classmethod
    def is_own_goal(cls, event: dict[str, Any]) -> bool:
        return cls.is_goal_event(event) and "own goal" in str(event.get("detail", "")).lower()

    @classmethod
    def is_penalty_shootout_goal(cls, event: dict[str, Any], fixture: dict[str, Any]) -> bool:
        status = str((fixture.get("fixture") or {}).get("status", {}).get("short", "")).upper()
        detail = str(event.get("detail", "")).lower()
        elapsed = cls.int_value((event.get("time") or {}).get("elapsed"))
        return status == "PEN" and "penalty" in detail and elapsed >= 120


def build_source_of_truth(
    match_date: date,
    output_dir: Path = DEFAULT_TRUTH_DIR,
    public_data_dir: Path = DEFAULT_PUBLIC_DATA_DIR,
    league_id: str = DEFAULT_LEAGUE_ID,
    season: str = DEFAULT_SEASON,
    fixture_ids: list[str] | None = None,
    matchday_id: str | None = None,
    refresh: bool = False,
    allow_incomplete: bool = False,
    ignore_public_data: bool = False,
) -> SourceTruthBuildResult:
    """Build the post-match truth bundle for one simulated matchday."""
    client = ApiFootballClient(raw_source_dir=DEFAULT_RAW_TRUTH_SOURCE_DIR)
    resolved = _resolve_fixture_scope(
        client=client,
        match_date=match_date,
        public_data_dir=public_data_dir,
        league_id=league_id,
        season=season,
        fixture_ids=fixture_ids or [],
        matchday_id=matchday_id,
        refresh=refresh,
        ignore_public_data=ignore_public_data,
    )
    fixtures = _fetch_fixture_details(client, resolved["fixture_ids"], refresh=refresh)
    incomplete_fixture_ids = _incomplete_fixture_ids(fixtures)
    if incomplete_fixture_ids and not allow_incomplete:
        raise RuntimeError(
            "Some fixtures are not finished yet: "
            + ", ".join(incomplete_fixture_ids)
            + ". Re-run after the matches finish or pass --allow-incomplete for inspection."
        )

    generated_at = _utc_now()
    truth = FootballTruthParser(
        matchday_id=resolved["matchday_id"],
        league_id=league_id,
        season=season,
        source_mode=resolved["source_mode"],
        match_date=match_date,
        fixture_ids=resolved["fixture_ids"],
        incomplete_fixture_ids=incomplete_fixture_ids,
    ).normalize(fixtures, generated_at=generated_at)

    run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    raw_payload = {
        "fetched_at": generated_at,
        "source_mode": resolved["source_mode"],
        "league_id": league_id,
        "season": season,
        "match_date": match_date.isoformat(),
        "fixture_ids": resolved["fixture_ids"],
        "fixtures": fixtures,
    }

    raw_path = output_dir / "raw" / run_id / "api_football_truth_raw.json"
    final_truth_path = output_dir / "final" / f"{resolved['matchday_id']}.truth.json"
    latest_truth_path = output_dir / "latest_truth.json"
    catalog_path = output_dir / "source_truth_catalog.md"
    by_date_path = output_dir / "by_date" / f"{match_date.isoformat()}.truth.json"

    _write_json(raw_path, raw_payload)
    _write_json(final_truth_path, truth)
    _write_json(latest_truth_path, truth)
    _write_json(by_date_path, truth)
    catalog_path.parent.mkdir(parents=True, exist_ok=True)
    catalog_path.write_text(_build_catalog(truth), encoding="utf-8")

    return SourceTruthBuildResult(
        output_dir=output_dir,
        latest_truth_path=latest_truth_path,
        final_truth_path=final_truth_path,
        raw_path=raw_path,
        catalog_path=catalog_path,
        matchday_id=resolved["matchday_id"],
        fixture_count=len(fixtures),
        player_count=len(truth["players"]),
        incomplete_fixture_ids=incomplete_fixture_ids,
    )


def create_source_truth_snapshot(run_dir: Path, source_truth_dir: Path = DEFAULT_TRUTH_DIR) -> SourceTruthSnapshot:
    """Copy the latest truth bundle into a scoring run folder."""
    latest_path = source_truth_dir / "latest_truth.json"
    catalog_path = source_truth_dir / "source_truth_catalog.md"
    if not latest_path.is_file():
        raise FileNotFoundError(f"Source truth has not been generated yet: {latest_path}")

    truth_dir = run_dir / "source_of_truth"
    truth_dir.mkdir(parents=True, exist_ok=True)
    copied = []
    for source_path in [latest_path, catalog_path]:
        if source_path.is_file():
            destination = truth_dir / source_path.name
            shutil.copy2(source_path, destination)
            copied.append(destination)
    return SourceTruthSnapshot(truth_dir=truth_dir, files=copied)


def _resolve_fixture_scope(
    *,
    client: ApiFootballClient,
    match_date: date,
    public_data_dir: Path,
    league_id: str,
    season: str,
    fixture_ids: list[str],
    matchday_id: str | None,
    refresh: bool,
    ignore_public_data: bool,
) -> dict[str, Any]:
    if fixture_ids:
        return {
            "fixture_ids": [str(item) for item in fixture_ids],
            "matchday_id": matchday_id or _default_matchday_id(season, match_date),
            "source_mode": "fixture_ids",
        }

    if not ignore_public_data:
        public_scope = _fixture_scope_from_public_data(public_data_dir, match_date)
        if public_scope is not None:
            if matchday_id:
                public_scope["matchday_id"] = matchday_id
            return public_scope

    payload = client.get(
        "fixtures",
        {"league": league_id, "season": season, "date": match_date.isoformat(), "timezone": TIMEZONE},
        refresh=refresh,
    )
    fixture_ids = [str(item["fixture"]["id"]) for item in payload.get("response") or []]
    return {
        "fixture_ids": fixture_ids,
        "matchday_id": matchday_id or _default_matchday_id(season, match_date),
        "source_mode": "date",
    }


def _fixture_scope_from_public_data(public_data_dir: Path, match_date: date) -> dict[str, Any] | None:
    archive_matchday_path = public_data_dir / "by_date" / match_date.isoformat() / "matchday.json"
    archive_scope = _fixture_scope_from_matchday_file(archive_matchday_path, match_date, "public_matchday_archive")
    if archive_scope is not None:
        return archive_scope

    index_scope = _fixture_scope_from_matchday_index(public_data_dir / "matchdays_index.json", match_date)
    if index_scope is not None:
        return index_scope

    latest_matchday_path = public_data_dir / "matchday.json"
    return _fixture_scope_from_matchday_file(latest_matchday_path, match_date, "public_matchday_latest")


def _fixture_scope_from_matchday_file(path: Path, match_date: date, source_mode: str) -> dict[str, Any] | None:
    if not path.is_file():
        return None

    try:
        matchday = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None

    matchday_id = str(matchday.get("matchday_id") or "")
    public_match_date = str(matchday.get("match_date") or "")
    expected_suffix = match_date.strftime("%Y%m%d")
    fixture_ids = [str(item) for item in matchday.get("fixture_ids") or []]
    if not fixture_ids:
        return None
    if public_match_date and public_match_date != match_date.isoformat():
        return None
    if not public_match_date and not matchday_id.endswith(expected_suffix):
        return None

    return {
        "fixture_ids": fixture_ids,
        "matchday_id": matchday_id,
        "source_mode": source_mode,
    }


def _fixture_scope_from_matchday_index(path: Path, match_date: date) -> dict[str, Any] | None:
    if not path.is_file():
        return None

    try:
        index = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None

    for entry in index.get("matchdays") or []:
        if entry.get("match_date") != match_date.isoformat():
            continue
        fixture_ids = [str(item) for item in entry.get("fixture_ids") or []]
        if not fixture_ids:
            return None
        return {
            "fixture_ids": fixture_ids,
            "matchday_id": str(entry.get("matchday_id") or _default_matchday_id(str(entry.get("season") or ""), match_date)),
            "source_mode": "public_matchday_index",
        }
    return None


def _fetch_fixture_details(client: ApiFootballClient, fixture_ids: list[str], refresh: bool) -> list[dict[str, Any]]:
    fixtures = []
    for fixture_id in fixture_ids:
        payload = client.get("fixtures", {"id": fixture_id, "timezone": TIMEZONE}, refresh=refresh)
        fixtures.extend(payload.get("response") or [])
    return fixtures


def _incomplete_fixture_ids(fixtures: list[dict[str, Any]]) -> list[str]:
    incomplete = []
    for fixture in fixtures:
        fixture_id = str((fixture.get("fixture") or {}).get("id"))
        status = str(((fixture.get("fixture") or {}).get("status") or {}).get("short") or "")
        if status not in FINISHED_STATUS:
            incomplete.append(fixture_id)
    return incomplete


def _build_catalog(truth: dict[str, Any]) -> str:
    lines = [
        "# Source Of Truth Catalog",
        "",
        f"Matchday ID: `{truth['matchday_id']}`",
        f"Match date: `{truth['match_date']}`",
        f"Complete: `{truth['state']['complete']}`",
        "",
        "## Files",
        "",
        "- `latest_truth.json`: normalized truth consumed by scoring.",
        "- `final/<matchday_id>.truth.json`: immutable copy for this matchday.",
        "- `by_date/<YYYY-MM-DD>.truth.json`: date-addressable copy.",
        "- `raw/<run_id>/api_football_truth_raw.json`: raw fixture detail snapshot.",
        "",
        "## Matches",
        "",
    ]
    if truth["matches"]:
        for match in truth["matches"]:
            score = match["score"]
            lines.append(
                f"- `{match['id']}`: {match['home_team']['name']} {score['home']}-{score['away']} {match['away_team']['name']}"
            )
    else:
        lines.append("- No matches found for this truth generation.")

    lines.extend(
        [
            "",
            "## Inventory",
            "",
            f"- Matches: {len(truth['matches'])}",
            f"- Player records: {len(truth['players'])}",
            f"- Incomplete fixture IDs: {len(truth['state']['incomplete_fixture_ids'])}",
            "",
        ]
    )
    return "\n".join(lines)


def _default_matchday_id(season: str, match_date: date) -> str:
    return f"wc-{season}-{match_date.strftime('%Y%m%d')}"


def _write_json(path: Path, payload: dict[str, Any] | list[Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate post-match source-of-truth data for scoring.")
    parser.add_argument("--match-date", required=True, help="Played matchday date in YYYY-MM-DD format.")
    parser.add_argument("--league-id", default=DEFAULT_LEAGUE_ID)
    parser.add_argument("--season", default=DEFAULT_SEASON)
    parser.add_argument("--matchday-id", default=None)
    parser.add_argument("--fixture-id", action="append", default=[], help="Explicit fixture ID. Can be passed more than once.")
    parser.add_argument("--out", type=Path, default=DEFAULT_TRUTH_DIR)
    parser.add_argument("--public-data-dir", type=Path, default=DEFAULT_PUBLIC_DATA_DIR)
    parser.add_argument("--refresh", action="store_true", help="Ignore raw response cache and call API-Football again.")
    parser.add_argument(
        "--allow-incomplete",
        action="store_true",
        help="Write truth even if one or more fixtures are not in a finished status.",
    )
    parser.add_argument(
        "--ignore-public-data",
        action="store_true",
        help="Resolve fixtures by API date instead of reusing the generated public matchday fixture IDs.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = build_source_of_truth(
        match_date=date.fromisoformat(args.match_date),
        output_dir=args.out,
        public_data_dir=args.public_data_dir,
        league_id=str(args.league_id),
        season=str(args.season),
        fixture_ids=[str(item) for item in args.fixture_id],
        matchday_id=args.matchday_id,
        refresh=args.refresh,
        allow_incomplete=args.allow_incomplete,
        ignore_public_data=args.ignore_public_data,
    )
    print(f"Source truth written: {result.output_dir}")
    print(f"Matchday: {result.matchday_id}")
    print(f"Matches: {result.fixture_count}")
    print(f"Player records: {result.player_count}")
    print(f"Latest truth: {result.latest_truth_path}")
    print(f"Final truth: {result.final_truth_path}")
    print(f"Raw API snapshot: {result.raw_path}")
    if result.incomplete_fixture_ids:
        print(f"Incomplete fixtures: {', '.join(result.incomplete_fixture_ids)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
