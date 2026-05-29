# Generate Valid Fantasy Cup Pick

You create one valid Fantasy Cup team submission JSON object from local public data.

## Team Identity

- `team_id`: `codex-local-demo`
- `team_name`: `Codex Local Demo`

## Inputs To Read

Read these files from the public data directory named in the prompt:

- `manifest.json` for the matchday id and data inventory.
- `matchday.json` for rules and position limits.
- `players.json` for eligible player `record_id` values.
- `risk_claims.json` for allowed risk play claim options.
- `answer_template.json` for the required output shape.

## Output Rules

- Produce exactly one final team submission.
- If the runner asks for a response, return only the JSON object; the runner will save it as `submission.json`.
- If the runner asks for file output, write exactly one final artifact named `submission.json`.
- The JSON must have `team_id`, `team_name`, `matchday_id`, and `answers`.
- `answers.fantasy_xi` must contain exactly 11 entries.
- Every Fantasy XI entry must use this shape: `{ "record_id": "match_id:player_id" }`.
- Each `record_id` must come from `players.json`.
- `answers.risk_play` may be `null`. Use `null` unless you are confident a risk claim can be copied correctly from `risk_claims.json`.
- `answers.strategy_summary` must be one short paragraph.
- Do not include markdown fences in `submission.json`.

## Pick Strategy

Prefer a balanced team that covers multiple matches and includes attacking players when player position or role data is available. If the data is sparse, prioritize producing a schema-valid submission over optimizing the score.
