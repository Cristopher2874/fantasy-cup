POINTS = {
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


def score_fantasy_xi(player_ids: list[str], matchday: dict) -> dict:
    player_lookup = {player["id"]: player for player in matchday.get("players", [])}
    events = matchday.get("player_events", {})
    player_scores = []
    total = 0

    for player_id in player_ids:
        player = player_lookup[player_id]
        event = events.get(player_id, {})
        points, breakdown = score_player(player, event)
        total += points
        player_scores.append(
            {
                "player_id": player_id,
                "name": player["name"],
                "position": player["position"],
                "team": player["team"],
                "points": points,
                "breakdown": breakdown,
            }
        )

    return {"total": total, "players": player_scores}


def score_player(player: dict, event: dict) -> tuple[int, list[dict]]:
    points = 0
    breakdown: list[dict] = []

    if event.get("starts"):
        points += add(breakdown, "Started", POINTS["starts"])
    if event.get("minutes", 0) >= 60:
        points += add(breakdown, "Played 60+ minutes", POINTS["plays_60"])
    if event.get("goals", 0):
        points += add(breakdown, "Goals", event["goals"] * POINTS["goal"])
    if event.get("assists", 0):
        points += add(breakdown, "Assists", event["assists"] * POINTS["assist"])
    if player["position"] in {"GK", "DEF"} and event.get("clean_sheet"):
        points += add(breakdown, "Clean sheet", POINTS["clean_sheet"])
    if player["position"] == "GK" and event.get("saves", 0) >= 3:
        points += add(breakdown, "Goalkeeper 3+ saves", POINTS["goalkeeper_saves"])
    if event.get("yellow_cards", 0):
        points += add(breakdown, "Yellow cards", event["yellow_cards"] * POINTS["yellow_card"])
    if event.get("red_cards", 0):
        points += add(breakdown, "Red cards", event["red_cards"] * POINTS["red_card"])
    if event.get("own_goals", 0):
        points += add(breakdown, "Own goals", event["own_goals"] * POINTS["own_goal"])

    return points, breakdown


def add(breakdown: list[dict], label: str, points: int) -> int:
    breakdown.append({"label": label, "points": points})
    return points
