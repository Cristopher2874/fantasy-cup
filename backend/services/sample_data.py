from pathlib import Path

from backend.config import settings
from backend.services.state_store import hash_token, utc_now


DEMO_TOKENS = {
    "TGR-001": "golden-demo-token",
    "TGR-002": "nebula-demo-token",
}


def build_mock_matchday(
    matchday_id: str = "MD-001",
    label: str = "Mock Matchday 1",
    match_date: str | None = None,
    stage: str = "league",
) -> dict:
    players = [
        player("P-GK-001", "Sofia Marin", "ESP", "Spain", "GK", "M-001", 88),
        player("P-GK-002", "Maya Keller", "GER", "Germany", "GK", "M-002", 76),
        player("P-DEF-001", "Lena Torres", "ESP", "Spain", "DEF", "M-001", 86),
        player("P-DEF-002", "Nora Weiss", "GER", "Germany", "DEF", "M-002", 83),
        player("P-DEF-003", "Clara Novak", "CRO", "Croatia", "DEF", "M-002", 79),
        player("P-DEF-004", "Iris Baum", "GER", "Germany", "DEF", "M-002", 75),
        player("P-DEF-005", "Paula Silva", "BRA", "Brazil", "DEF", "M-001", 73),
        player("P-DEF-006", "Ana Rocha", "BRA", "Brazil", "DEF", "M-001", 70),
        player("P-MID-001", "Marta Leon", "ESP", "Spain", "MID", "M-001", 90),
        player("P-MID-002", "Eva Brandt", "GER", "Germany", "MID", "M-002", 85),
        player("P-MID-003", "Renata Costa", "BRA", "Brazil", "MID", "M-001", 82),
        player("P-MID-004", "Ivana Petric", "CRO", "Croatia", "MID", "M-002", 78),
        player("P-MID-005", "Lucia Ramos", "ESP", "Spain", "MID", "M-001", 74),
        player("P-MID-006", "Tessa Vogel", "GER", "Germany", "MID", "M-002", 71),
        player("P-FWD-001", "Bianca Alves", "BRA", "Brazil", "FWD", "M-001", 91),
        player("P-FWD-002", "Greta Hartmann", "GER", "Germany", "FWD", "M-002", 87),
        player("P-FWD-003", "Camila Vega", "ESP", "Spain", "FWD", "M-001", 81),
        player("P-FWD-004", "Daria Kovac", "CRO", "Croatia", "FWD", "M-002", 77),
    ]
    player_events = {
        "P-GK-001": event(starts=True, minutes=90, clean_sheet=False, saves=4),
        "P-GK-002": event(starts=True, minutes=90, clean_sheet=True, saves=3),
        "P-DEF-001": event(starts=True, minutes=90, clean_sheet=False, assists=1),
        "P-DEF-002": event(starts=True, minutes=90, clean_sheet=True),
        "P-DEF-003": event(starts=True, minutes=90, clean_sheet=False, yellow_cards=1),
        "P-DEF-004": event(starts=True, minutes=62, clean_sheet=True),
        "P-DEF-005": event(starts=True, minutes=90, clean_sheet=False),
        "P-DEF-006": event(starts=False, minutes=19),
        "P-MID-001": event(starts=True, minutes=88, goals=1),
        "P-MID-002": event(starts=True, minutes=90, assists=1),
        "P-MID-003": event(starts=True, minutes=90, goals=1, yellow_cards=1),
        "P-MID-004": event(starts=True, minutes=77),
        "P-MID-005": event(starts=False, minutes=34, assists=1),
        "P-MID-006": event(starts=True, minutes=59),
        "P-FWD-001": event(starts=True, minutes=90, goals=1, assists=1),
        "P-FWD-002": event(starts=True, minutes=84, goals=2),
        "P-FWD-003": event(starts=True, minutes=66),
        "P-FWD-004": event(starts=True, minutes=71, red_cards=1),
    }
    matches = [
        {
            "id": "M-001",
            "home_team_id": "ESP",
            "home_team": "Spain",
            "away_team_id": "BRA",
            "away_team": "Brazil",
            "kickoff": f"{match_date or '2026-06-12'}T18:00:00Z",
            "public": True,
            "score": {"home": 2, "away": 2},
        },
        {
            "id": "M-002",
            "home_team_id": "GER",
            "home_team": "Germany",
            "away_team_id": "CRO",
            "away_team": "Croatia",
            "kickoff": f"{match_date or '2026-06-12'}T21:00:00Z",
            "public": True,
            "score": {"home": 3, "away": 0},
        },
    ]
    risk_claims = [
        risk_claim("RC-001", "green", "M-001 has 2 or more total goals", ["match_id"], {"match_id": "M-001"}, True),
        risk_claim("RC-002", "yellow", "Germany scores first", ["match_id", "team_id"], {"match_id": "M-002", "team_id": "GER"}, True),
        risk_claim("RC-003", "red", "Selected player scores two or more goals", ["match_id", "player_id"], {"match_id": "M-002", "player_id": "P-FWD-002"}, True),
        risk_claim("RC-004", "yellow", "Croatia keeps a clean sheet", ["match_id", "team_id"], {"match_id": "M-002", "team_id": "CRO"}, False),
    ]
    return {
        "id": matchday_id,
        "label": label,
        "match_date": match_date or "2026-06-12",
        "stage": stage,
        "status": "draft",
        "players": players,
        "matches": matches,
        "risk_claims": risk_claims,
        "player_events": player_events,
        "created_at": utc_now(),
    }


def seed_demo(store) -> dict:
    created = {"teams": [], "snapshots": [], "matchdays": []}

    existing_team_ids = {team["id"] for team in store.read("teams")}
    demo_teams = [
        ("TGR-001", "The Golden Robots", ["Ada Rivera", "Noah Chen"], "golden-demo-token"),
        ("TGR-002", "Nebula Set Pieces", ["Mina Patel", "Oscar Diaz"], "nebula-demo-token"),
    ]
    for team_id, name, members, token in demo_teams:
        if team_id in existing_team_ids:
            continue
        team = {
            "id": team_id,
            "name": name,
            "members": members,
            "token_hash": hash_token(token),
            "submission_method": "repo",
            "repo_url": "https://github.com/example/fantasy-cup-demo-skills",
            "created_at": utc_now(),
        }
        store.append("teams", team)
        created["teams"].append({key: value for key, value in team.items() if key != "token_hash"})

    existing_snapshot_ids = {snapshot["id"] for snapshot in store.read("snapshots")}
    for index, team_id in enumerate(["TGR-001", "TGR-002"], start=1):
        snapshot_id = f"SNP-DEMO-{index:03d}"
        if snapshot_id in existing_snapshot_ids:
            continue
        snapshot_dir = settings.snapshots_dir / team_id / snapshot_id
        write_demo_skill(snapshot_dir, team_id)
        snapshot = {
            "id": snapshot_id,
            "team_id": team_id,
            "submission_id": "SUB-DEMO",
            "matchday_id": None,
            "source": "demo",
            "repo_url": "https://github.com/example/fantasy-cup-demo-skills",
            "path": str(snapshot_dir.relative_to(settings.project_root)),
            "accepted": True,
            "errors": [],
            "warnings": [],
            "created_at": utc_now(),
        }
        store.append("snapshots", snapshot)
        created["snapshots"].append(snapshot)

    if not store.find_by_id("matchdays", "MD-001"):
        matchday = build_mock_matchday()
        store.append("matchdays", matchday)
        created["matchdays"].append(matchday)

    return {"created": created, "demo_tokens": DEMO_TOKENS}


def write_demo_skill(snapshot_dir: Path, team_id: str) -> None:
    skill_dir = snapshot_dir / "skills" / "phase-one-demo"
    skill_dir.mkdir(parents=True, exist_ok=True)
    (snapshot_dir / "README.md").write_text(
        f"# Demo skill package for {team_id}\n\nThis package is generated for the local POC.\n",
        encoding="utf-8",
    )
    (skill_dir / "SKILL.md").write_text(
        "---\nname: phase-one-demo\ndescription: Deterministic local demo skill.\n---\n\n"
        "Pick a valid Fantasy XI from the official matchday files, choose one risk claim when useful, "
        "and summarize the strategy in one short paragraph.\n",
        encoding="utf-8",
    )


def player(player_id: str, name: str, team_id: str, team: str, position: str, match_id: str, mock_rank: int) -> dict:
    return {
        "id": player_id,
        "name": name,
        "team_id": team_id,
        "team": team,
        "position": position,
        "match_id": match_id,
        "eligible": True,
        "mock_rank": mock_rank,
    }


def event(
    starts: bool,
    minutes: int,
    goals: int = 0,
    assists: int = 0,
    clean_sheet: bool = False,
    saves: int = 0,
    yellow_cards: int = 0,
    red_cards: int = 0,
    own_goals: int = 0,
) -> dict:
    return {
        "starts": starts,
        "minutes": minutes,
        "goals": goals,
        "assists": assists,
        "clean_sheet": clean_sheet,
        "saves": saves,
        "yellow_cards": yellow_cards,
        "red_cards": red_cards,
        "own_goals": own_goals,
    }


def risk_claim(claim_id: str, category: str, label: str, required_fields: list[str], fields: dict, outcome: bool) -> dict:
    claim = {
        "id": claim_id,
        "category": category,
        "label": label,
        "required_fields": required_fields,
        "outcome": outcome,
    }
    claim.update(fields)
    return claim
