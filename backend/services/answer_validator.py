from collections import Counter


POSITION_RULES = {
    "GK": (1, 1),
    "DEF": (3, 5),
    "MID": (3, 5),
    "FWD": (1, 3),
}


def validate_answers(answers: dict, matchday: dict) -> dict:
    result = {
        "valid": True,
        "sections": {
            "fantasy_xi": validate_fantasy_xi(answers.get("fantasy_xi"), matchday),
            "risk_play": validate_risk_play(answers.get("risk_play"), matchday),
            "strategy_summary": validate_strategy_summary(answers.get("strategy_summary")),
        },
    }
    result["valid"] = all(section["valid"] for section in result["sections"].values())
    return result


def validate_fantasy_xi(fantasy_xi: object, matchday: dict) -> dict:
    errors: list[str] = []
    details = {"position_counts": {}}

    if not isinstance(fantasy_xi, list):
        return {"valid": False, "errors": ["fantasy_xi must be an array"], "details": details}

    if len(fantasy_xi) != 11:
        errors.append("fantasy_xi must contain exactly 11 players")
    if len(set(fantasy_xi)) != len(fantasy_xi):
        errors.append("fantasy_xi must not contain duplicate player IDs")

    player_lookup = {
        player["id"]: player
        for player in matchday.get("players", [])
        if player.get("eligible", True)
    }
    selected_players = []
    for player_id in fantasy_xi:
        if player_id not in player_lookup:
            errors.append(f"Unknown or ineligible player ID: {player_id}")
        else:
            selected_players.append(player_lookup[player_id])

    counts = Counter(player["position"] for player in selected_players)
    details["position_counts"] = dict(counts)
    for position, (minimum, maximum) in POSITION_RULES.items():
        count = counts.get(position, 0)
        if count < minimum or count > maximum:
            if minimum == maximum:
                errors.append(f"{position} count must be exactly {minimum}")
            else:
                errors.append(f"{position} count must be between {minimum} and {maximum}")

    return {"valid": not errors, "errors": errors, "details": details}


def validate_risk_play(risk_play: object, matchday: dict) -> dict:
    if risk_play is None:
        return {"valid": True, "errors": [], "details": {"status": "skipped"}}

    errors: list[str] = []
    if not isinstance(risk_play, dict):
        return {"valid": False, "errors": ["risk_play must be an object or null"], "details": {}}

    claim_id = risk_play.get("claim_id")
    claim_lookup = {claim["id"]: claim for claim in matchday.get("risk_claims", [])}
    claim = claim_lookup.get(claim_id)
    if not claim:
        return {"valid": False, "errors": [f"Unknown risk claim ID: {claim_id}"], "details": {}}

    for field in claim.get("required_fields", []):
        if field not in risk_play:
            errors.append(f"risk_play missing required field: {field}")
        elif field in claim and risk_play[field] != claim[field]:
            errors.append(f"risk_play field {field} must match the selected claim")

    return {
        "valid": not errors,
        "errors": errors,
        "details": {"claim_id": claim_id, "category": claim.get("category")},
    }


def validate_strategy_summary(strategy_summary: object) -> dict:
    warnings: list[str] = []
    errors: list[str] = []
    if not isinstance(strategy_summary, str) or not strategy_summary.strip():
        errors.append("strategy_summary must be a non-empty string")
    elif len(strategy_summary) > 1000:
        warnings.append("strategy_summary is long for the local POC")
    return {"valid": not errors, "errors": errors, "warnings": warnings, "details": {}}
