from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TRUTH_PATH = ROOT / "scoring" / "truth_data" / "latest_truth.json"
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parent / "public_data"

SCHEMA_VERSION = "fantasy-cup-public-context-v1"

POSITION_RULES = {
    "GK": {"min": 1, "max": 1, "label": "Goalkeeper"},
    "DEF": {"min": 3, "max": 5, "label": "Defender"},
    "MID": {"min": 3, "max": 5, "label": "Midfielder"},
    "FWD": {"min": 1, "max": 3, "label": "Forward"},
}

RISK_DESCRIPTIONS = {
    "match_2plus_goals": "The selected match finishes with at least 2 total goals.",
    "no_goal_first_10": "No goal is scored from minute 1 through minute 10.",
    "goal_before_halftime": "At least one goal is scored before halftime.",
    "match_2plus_cards": "The selected match has at least 2 card events.",
    "no_goal_stoppage_time": "No goal is scored in first-half or second-half stoppage time.",
    "both_teams_score": "Both teams score at least once.",
    "match_over_2_5_goals": "The selected match finishes with 3 or more total goals.",
    "team_scores_first": "The selected team scores the first countable goal.",
    "player_scores": "The selected player scores at least one non-own goal.",
    "match_2plus_yellow_cards": "The selected match has at least 2 yellow-card events.",
    "exact_score": "The selected match finishes with the submitted home and away score.",
    "player_scores_2plus": "The selected player scores at least 2 non-own goals.",
    "team_wins_by_3plus": "The selected team wins by at least 3 goals.",
    "team_comeback_win": "The selected team concedes first and still wins the match.",
    "red_card_shown": "At least one red-card or second-yellow-red event is shown.",
    "match_goes_to_extra_time": "The knockout match reaches extra time.",
    "match_goes_to_penalties": "The knockout match reaches a penalty shootout.",
}

CLAIMS_REQUIRING_KNOCKOUT = {
    "match_goes_to_extra_time",
    "match_goes_to_penalties",
}

TEAM_PARAMETERIZED_CLAIMS = {
    "team_scores_first",
    "team_wins_by_3plus",
    "team_comeback_win",
}

PLAYER_PARAMETERIZED_CLAIMS = {
    "player_scores",
    "player_scores_2plus",
}


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any] | list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def public_match(match: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(match["id"]),
        "provider": match.get("provider"),
        "provider_fixture_id": str(match.get("provider_fixture_id", match["id"])),
        "round": match.get("round"),
        "stage": match.get("stage"),
        "kickoff": match.get("kickoff"),
        "home_team": public_team_ref(match.get("home_team", {})),
        "away_team": public_team_ref(match.get("away_team", {})),
    }


def public_team_ref(team: dict[str, Any]) -> dict[str, str | None]:
    return {
        "id": str(team.get("id")),
        "name": team.get("name"),
    }


def build_matches(truth: dict[str, Any]) -> list[dict[str, Any]]:
    return [public_match(match) for match in truth.get("matches", [])]


def build_teams(matches: list[dict[str, Any]]) -> list[dict[str, Any]]:
    teams: dict[str, dict[str, Any]] = {}

    for match in matches:
        for side in ("home_team", "away_team"):
            team = match[side]
            team_id = str(team["id"])
            entry = teams.setdefault(
                team_id,
                {
                    "id": team_id,
                    "name": team["name"],
                    "matches": [],
                },
            )
            opponent_side = "away_team" if side == "home_team" else "home_team"
            entry["matches"].append(
                {
                    "match_id": match["id"],
                    "side": "home" if side == "home_team" else "away",
                    "opponent_team_id": str(match[opponent_side]["id"]),
                    "opponent": match[opponent_side]["name"],
                }
            )

    return sorted(teams.values(), key=lambda item: (item["name"] or "", item["id"]))


def build_players(truth: dict[str, Any]) -> list[dict[str, Any]]:
    players = []
    for player in truth.get("players", []):
        players.append(
            {
                "record_id": player["record_id"],
                "match_id": str(player["match_id"]),
                "player_id": str(player["id"]),
                "name": player.get("name"),
                "team_id": str(player.get("team_id")),
                "team": player.get("team"),
                "position": player.get("position"),
            }
        )
    return sorted(players, key=lambda item: (item["match_id"], item["team"] or "", item["name"] or ""))


def build_risk_claims(truth: dict[str, Any], matches: list[dict[str, Any]]) -> dict[str, Any]:
    capabilities = truth.get("capabilities", {}).get("risk_claims", {})
    claim_types = []
    available_claims = []

    for claim_id, capability in sorted(capabilities.items()):
        claim_types.append(
            {
                "claim_id": claim_id,
                "category": capability.get("category"),
                "required_fields": capability.get("required_fields", []),
                "api_status": capability.get("api_status"),
                "description": RISK_DESCRIPTIONS.get(claim_id, "Risk Play claim."),
            }
        )

    for match in matches:
        team_options = [match["home_team"], match["away_team"]]
        for claim_id, capability in sorted(capabilities.items()):
            if claim_id in CLAIMS_REQUIRING_KNOCKOUT and match.get("stage") != "knockout":
                continue

            claim = {
                "claim_key": f"{match['id']}:{claim_id}",
                "claim_id": claim_id,
                "match_id": match["id"],
                "match_label": f"{match['home_team']['name']} vs {match['away_team']['name']}",
                "category": capability.get("category"),
                "required_fields": capability.get("required_fields", []),
                "description": RISK_DESCRIPTIONS.get(claim_id, "Risk Play claim."),
                "parameters": {
                    "match_id": match["id"],
                },
            }

            if claim_id in TEAM_PARAMETERIZED_CLAIMS:
                claim["parameter_options"] = {
                    "team_id": team_options,
                }
            elif claim_id in PLAYER_PARAMETERIZED_CLAIMS:
                claim["parameter_options"] = {
                    "player_id": {
                        "source_file": "players.json",
                        "filter": {"match_id": match["id"]},
                    }
                }
            elif claim_id == "exact_score":
                claim["parameter_options"] = {
                    "home_score": "non-negative integer",
                    "away_score": "non-negative integer",
                }

            available_claims.append(claim)

    return {
        "schema_version": SCHEMA_VERSION,
        "matchday_id": truth.get("matchday_id"),
        "claim_types": claim_types,
        "available_claims": available_claims,
        "stake_rules": {
            "green": "15% of the team's points before the matchday",
            "yellow": "25% of the team's points before the matchday",
            "red": "35% of the team's points before the matchday",
        },
    }


def build_matchday(truth: dict[str, Any], matches: list[dict[str, Any]], generated_at: str) -> dict[str, Any]:
    source = truth.get("source", {})
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "matchday_id": truth.get("matchday_id"),
        "competition": {
            "provider": source.get("provider"),
            "league_id": source.get("league_id"),
            "season": source.get("season"),
        },
        "fixture_ids": [match["id"] for match in matches],
        "public_run_mode": "historical fixtures redacted as pre-match context",
        "fantasy_xi_rules": {
            "selection_count": 11,
            "selection_id": "Use players[].record_id from players.json.",
            "positions": POSITION_RULES,
        },
        "point_rules": truth.get("point_rules", {}),
        "risk_play_rules": {
            "optional": True,
            "select_at_most": 1,
            "claim_source": "risk_claims.json",
        },
        "hidden_until_scoring": [
            "fixture status and final score",
            "lineups and starters",
            "event timeline",
            "player minutes",
            "goals, assists, cards, saves, own goals, and clean-sheet truth",
            "fantasy points and point breakdowns",
            "risk claim outcomes and evidence",
        ],
    }


def build_manifest(truth: dict[str, Any], generated_at: str) -> dict[str, Any]:
    source = truth.get("source", {})
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "matchday_id": truth.get("matchday_id"),
        "source": {
            "provider": source.get("provider"),
            "league_id": source.get("league_id"),
            "season": source.get("season"),
            "source_mode": source.get("source_mode"),
            "fixture_ids": source.get("fixture_ids", []),
        },
        "files": {
            "matchday": "matchday.json",
            "matches": "matches.json",
            "teams": "teams.json",
            "players": "players.json",
            "risk_claims": "risk_claims.json",
            "answer_template": "answer_template.json",
            "catalog": "public_data_catalog.md",
        },
        "redaction": "Public files omit post-match outcomes and scoring truth.",
    }


def build_answer_template(matchday_id: str | None) -> dict[str, Any]:
    return {
        "team_id": "replace-with-team-id",
        "team_name": "Replace With Team Name",
        "matchday_id": matchday_id,
        "answers": {
            "fantasy_xi": [{"record_id": f"replace-with-player-record-id-{index}"} for index in range(1, 12)],
            "risk_play": None,
            "strategy_summary": "One short paragraph explaining the picks.",
        },
    }


def build_catalog(
    matchday: dict[str, Any],
    matches: list[dict[str, Any]],
    teams: list[dict[str, Any]],
    players: list[dict[str, Any]],
    risk_claims: dict[str, Any],
) -> str:
    lines = [
        "# Public Data Catalog",
        "",
        f"Matchday ID: `{matchday['matchday_id']}`",
        "",
        "## Files",
        "",
        "- `matchday.json`: rules, scoring values, fixture IDs, and hidden-data policy.",
        "- `matches.json`: one record per fixture available for this simulated matchday.",
        "- `teams.json`: stable team IDs and per-fixture opponent context.",
        "- `players.json`: eligible player records; submit `record_id` values in Fantasy XI.",
        "- `risk_claims.json`: allowed Risk Play claim types and match-specific claim options.",
        "- `answer_template.json`: minimal single-team answer shape.",
        "",
        "## Match Scope",
        "",
    ]

    for match in matches:
        lines.append(
            f"- `{match['id']}`: {match['home_team']['name']} vs {match['away_team']['name']} "
            f"({match['round']}, {match['kickoff']})"
        )

    lines.extend(
        [
            "",
            "## Player Eligibility",
            "",
            f"`players.json` currently contains {len(players)} match-specific player records.",
            "A `record_id` combines `match_id:player_id` so the scorer can disambiguate players",
            "who appear in more than one test fixture.",
            "",
            "Position limits:",
            "",
        ]
    )

    for position, rule in matchday["fantasy_xi_rules"]["positions"].items():
        lines.append(f"- `{position}`: {rule['min']} to {rule['max']} ({rule['label']})")

    lines.extend(
        [
            "",
            "## Risk Play",
            "",
            f"`risk_claims.json` contains {len(risk_claims['claim_types'])} claim types and "
            f"{len(risk_claims['available_claims'])} match-specific claim options.",
            "A team may submit one Risk Play object or `null`.",
            "",
            "## Hidden Until Scoring",
            "",
        ]
    )

    for item in matchday["hidden_until_scoring"]:
        lines.append(f"- {item}")

    lines.extend(
        [
            "",
            "## Teams In Scope",
            "",
        ]
    )

    for team in teams:
        match_ids = ", ".join(match["match_id"] for match in team["matches"])
        lines.append(f"- `{team['id']}`: {team['name']} (matches: {match_ids})")

    return "\n".join(lines) + "\n"


def build_public_context(truth_path: Path, output_dir: Path) -> list[Path]:
    truth = load_json(truth_path)
    generated_at = utc_now()

    matches = build_matches(truth)
    teams = build_teams(matches)
    players = build_players(truth)
    risk_claims = build_risk_claims(truth, matches)
    matchday = build_matchday(truth, matches, generated_at)
    manifest = build_manifest(truth, generated_at)
    answer_template = build_answer_template(truth.get("matchday_id"))
    catalog = build_catalog(matchday, matches, teams, players, risk_claims)

    outputs: list[tuple[Path, dict[str, Any] | list[dict[str, Any]] | str]] = [
        (output_dir / "manifest.json", manifest),
        (output_dir / "matchday.json", matchday),
        (output_dir / "matches.json", matches),
        (output_dir / "teams.json", teams),
        (output_dir / "players.json", players),
        (output_dir / "risk_claims.json", risk_claims),
        (output_dir / "answer_template.json", answer_template),
        (output_dir / "public_data_catalog.md", catalog),
    ]

    written = []
    for path, payload in outputs:
        if isinstance(payload, str):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(payload, encoding="utf-8")
        else:
            write_json(path, payload)
        written.append(path)

    return written


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build redacted public team-submission context.")
    parser.add_argument(
        "--truth",
        type=Path,
        default=DEFAULT_TRUTH_PATH,
        help="Path to normalized scoring truth JSON.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory for public context files.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    written = build_public_context(args.truth, args.out)
    for path in written:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
