def rebuild_leaderboard(store) -> list[dict]:
    teams = store.read("teams")
    latest_runs = latest_runs_by_team_matchday(store.read("runs")).values()

    rows = []
    for team in teams:
        team_runs = [run for run in latest_runs if run["team_id"] == team["id"]]
        fantasy_points = sum(run.get("fantasy_points", 0) for run in team_runs)
        risk_points = sum(run.get("risk_points", 0) for run in team_runs)
        bracket_points = sum(run.get("bracket_points", 0) for run in team_runs)
        total_points = fantasy_points + risk_points + bracket_points
        risk_record = build_risk_record(team_runs)
        rows.append(
            {
                "rank": 0,
                "team_id": team["id"],
                "team_name": team["name"],
                "total_points": round(total_points, 2),
                "fantasy_points": round(fantasy_points, 2),
                "risk_points": round(risk_points, 2),
                "bracket_points": round(bracket_points, 2),
                "risk_record": risk_record,
                "runs": len(team_runs),
            }
        )

    rows.sort(key=lambda row: row["total_points"], reverse=True)
    for index, row in enumerate(rows, start=1):
        row["rank"] = index
    store.write("leaderboard", rows)
    return rows


def team_points_before_matchday(store, team_id: str, matchday_id: str) -> float:
    total = 0.0
    for run in latest_runs_by_team_matchday(store.read("runs")).values():
        if run["team_id"] == team_id and run["matchday_id"] != matchday_id:
            total += run.get("total_points", 0)
    return total


def latest_runs_by_team_matchday(runs: list[dict]) -> dict[tuple[str, str], dict]:
    latest = {}
    for run in sorted(runs, key=lambda item: item.get("created_at", "")):
        latest[(run["team_id"], run["matchday_id"])] = run
    return latest


def build_risk_record(runs: list[dict]) -> str:
    wins = sum(1 for run in runs if run.get("risk_outcome") == "correct")
    losses = sum(1 for run in runs if run.get("risk_outcome") == "incorrect")
    skipped = sum(1 for run in runs if run.get("risk_outcome") == "skipped")
    return f"{wins}-{losses}-{skipped}"
