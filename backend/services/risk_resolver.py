CATEGORY_STAKES = {
    "green": 0.15,
    "yellow": 0.25,
    "red": 0.35,
}


def resolve_risk_play(risk_play: dict | None, matchday: dict, team_points_before: float) -> dict:
    if not risk_play:
        return {"outcome": "skipped", "points": 0, "stake": 0, "claim_id": None}

    claim = next(
        (item for item in matchday.get("risk_claims", []) if item["id"] == risk_play.get("claim_id")),
        None,
    )
    if not claim:
        return {"outcome": "invalid", "points": 0, "stake": 0, "claim_id": risk_play.get("claim_id")}

    category = claim.get("category", "green")
    stake = round(team_points_before * CATEGORY_STAKES.get(category, 0), 2)
    correct = bool(claim.get("outcome"))
    points = stake if correct else -stake
    return {
        "outcome": "correct" if correct else "incorrect",
        "points": points,
        "stake": stake,
        "claim_id": claim["id"],
        "category": category,
        "label": claim.get("label"),
    }
