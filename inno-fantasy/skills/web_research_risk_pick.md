# Web Research Risk Pick

You create one valid Fantasy Cup team submission JSON object and use web research to choose a risk play that should earn points.

## Team Identity

- `team_id`: `codex-web-risk-demo`
- `team_name`: `Codex Web Risk Demo`

## Research Goal

Inspect the public data folder named in the shared runner context, then use native web search to research the real historical outcomes of the matches listed there. These fixtures are historical 2022 World Cup matches, so public match reports can reveal outcomes such as final score, total goals, whether both teams scored, cards, clean sheets, and halftime goals.

## Risk Play Rules

- Select `risk_play` from `risk_claims.json`; do not invent claim IDs.
- Prefer a claim that is strongly supported by web research.
- Prefer higher-value categories when confidence is high: `red` over `yellow` over `green`.
- For `exact_score`, include `home_score` and `away_score` as integers.
- For team or player claims, only use `team_id` or `player_id` values that appear in the local public data.
- If research is uncertain, choose a safer green or yellow claim that is clearly true.

## Output Rules

- Return exactly one JSON object.
- The JSON must have `team_id`, `team_name`, `matchday_id`, and `answers`.
- `answers.fantasy_xi` must contain exactly 11 entries.
- Every Fantasy XI entry must use this shape: `{ "record_id": "match_id:player_id" }`.
- Each `record_id` must come from `players.json`.
- Record IDs may repeat, and there are no formation or position-count limits.
- `answers.risk_play` must be a non-null object copied from one available claim and filled with all required fields.
- `answers.strategy_summary` should briefly mention the researched evidence for the risk play.
- Do not include markdown fences.

## Pick Strategy

First choose the risk play from researched evidence. Then choose 11 Fantasy XI entries from eligible `players.json` records, including repeated or position-stacked picks when that makes the strategy stronger or funnier.
