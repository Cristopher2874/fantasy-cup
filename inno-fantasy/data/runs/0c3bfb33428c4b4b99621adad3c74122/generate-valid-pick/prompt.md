You are Codex CLI running a Fantasy Cup skill execution.

Execute the submitted skill using only the local public data snapshot and schema
listed below. Return only the final team submission JSON object; do not wrap it
in markdown fences and do not include commentary.

Run context:
- Validation job id: 0c3bfb33428c4b4b99621adad3c74122
- Team id from upload form: not-provided
- Skill name: generate-valid-pick
- Skill folder: C:\Users\Cristopher Hdz\Documents\projects\fantasy-cup\inno-fantasy\data\runs\0c3bfb33428c4b4b99621adad3c74122\generate-valid-pick\skill
- Public data folder: C:\Users\Cristopher Hdz\Documents\projects\fantasy-cup\inno-fantasy\data\runs\0c3bfb33428c4b4b99621adad3c74122\generate-valid-pick\public_data
- Submission schema: C:\Users\Cristopher Hdz\Documents\projects\fantasy-cup\inno-fantasy\data\runs\0c3bfb33428c4b4b99621adad3c74122\generate-valid-pick\schemas\team_submission.schema.json
- Public files available: answer_template.json, manifest.json, matchday.json, matchdays_index.json, matches.json, player_prior_stats.json, players.json, prior_matches.json, public_data_catalog.md, risk_claims.json, team_prior_stats.json, teams.json

Platform-specific guidance:
This run is using Windows Codex CLI workarounds.

When reading local files, use simple read-only PowerShell commands only:
- Use the exact Skill folder, Public data folder, and Submission schema paths
  listed in the prompt.
- `Get-ChildItem -Force -LiteralPath '<public data folder from prompt>'`
- `Get-Content -Raw -LiteralPath '<public data folder from prompt>\manifest.json'`
- `Get-Content -Raw -LiteralPath '<public data folder from prompt>\matchday.json'`
- `Get-Content -Raw -LiteralPath '<public data folder from prompt>\players.json'`
- `Get-Content -Raw -LiteralPath '<public data folder from prompt>\risk_claims.json'`
- `Get-Content -Raw -LiteralPath '<submission schema path from prompt>'`

Avoid compound PowerShell scripts, variables, loops, pipelines, ConvertFrom-Json,
Join-Path, redirection, Python, Node, or commands that would require approval.
If Windows sandbox setup fails before a command starts, report the failure rather
than guessing local `record_id` values from web search.

Output contract:
- Return exactly one JSON object.
- The object must have `team_id`, `team_name`, `matchday_id`, and `answers`.
- Use the upload team id `not-provided` as `team_id` when it is provided.
- `answers.fantasy_xi` must contain exactly 11 entries.
- Every Fantasy XI entry must use this shape: { "record_id": "match_id:player_id" }.
- Every `record_id` must be present in `players.json`.
- `answers.risk_play` must be `null` or a valid risk claim object from `risk_claims.json`.
- `answers.strategy_summary` must be a non-empty string.

Submitted skill:
---
name: generate-valid-pick
description: Selects a valid Fantasy XI from the provided public matchday data.
---

# Generate Valid Fantasy Cup Pick

You create one valid Fantasy Cup team submission JSON object from local public data.

## Team Identity

- `team_id`: `codex-local-demo`
- `team_name`: `Codex Local Demo`

## Inputs To Read

Inspect the public data folder named in the shared runner context. Read these files from that folder:

- `manifest.json` for the matchday id and data inventory.
- `matchday.json` for rules and position limits.
- `players.json` for eligible player `record_id` values.
- `risk_claims.json` for allowed risk play claim options.
- `answer_template.json` for the required output shape.
- The submission schema path from the shared context if you need to check the final JSON contract.

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

