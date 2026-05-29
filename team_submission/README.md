# Team Submission Public Data

This folder is the team-facing source of truth for the local skill ingestion,
execution, and submission playtest. It is intentionally separate from
`scoring/`, which owns final truth and scoring, and from `playtest_app/`, which
owns the browser-based test UI.

The current playtest uses the fixture IDs configured in
`scoring/daily_truth_pipeline.py` and exposes them as a simulated upcoming
matchday. The source fixtures are historical World Cup 2022 matches, but the
files in `public_data/` are shaped like pre-match artifacts: they include valid
IDs, match context, player eligibility, scoring rules, and risk claim templates;
they do not include scores, events, minutes, lineups, player fantasy points, or
risk outcomes.

Because these are historical fixtures, web-capable agents can still discover
real outcomes externally. That is useful for this phase because it tests whether
skills can combine the local source of truth with public research, while keeping
the local artifact boundary honest.

## What A Team Skill Should Read

Point the participant skill at this folder first:

```text
team_submission/public_data/
```

Important files:

| File | Purpose |
| --- | --- |
| `manifest.json` | Index of the public files and the fixture IDs in scope. |
| `matchday.json` | Matchday rules, position limits, scoring rules, and hidden-data policy. |
| `matches.json` | Public fixture context: match IDs, kickoff, round, teams, and stage. |
| `teams.json` | Team IDs and which fixtures each team appears in. |
| `players.json` | Eligible player records. Use `record_id` in Fantasy XI picks. |
| `risk_claims.json` | Allowed Risk Play claim types expanded across the public matches. |
| `answer_template.json` | Minimal JSON shape a skill should produce. |
| `public_data_catalog.md` | Plain-English guide to the available fields. |

## Expected Team Output

For the current scorer, a team answer should be wrapped later into the batch
format used by `scoring/mock_team_claims_2022.json`. A single team skill should
produce this inner shape:

```json
{
  "team_id": "example-team",
  "team_name": "Example Team",
  "matchday_id": "truth-test-world-cup-2022",
  "answers": {
    "fantasy_xi": [
      { "record_id": "979139:278" }
    ],
    "risk_play": null,
    "strategy_summary": "Short explanation of the pick logic."
  }
}
```

`fantasy_xi` must contain exactly 11 selections. Prefer
`{ "record_id": "match_id:player_id" }` because several players appear in more
than one test fixture.

## Pre-Match Stats Worth Providing

The current public artifact includes the minimum fair context required to make a
valid autonomous pick. API-Football can also support richer pre-match context in
future iterations:

- Competition coverage flags from `/leagues` so the app knows which data exists.
- Schedule and round data from `/fixtures` and `/fixtures/rounds`.
- Team identities and stable team IDs from `/teams`.
- Player profiles and season statistics from `/players`.
- Team form summaries from `/teams/statistics` with the `date` parameter set to
  the cutoff date.
- Standings from `/standings`, where available.
- Injury and suspension reports from `/injuries`, where coverage allows it.
- Provider predictions from `/predictions`, if organizers decide that API model
  output should be visible to everyone.
- Pre-match odds from `/odds`, if odds coverage and tournament policy allow it.

For fairness, any data that can directly resolve the game after kickoff should
stay out of public pre-run artifacts: final scores, event timelines, lineups
when the cutoff is before lineup release, player minutes, goals, assists, cards,
saves, own goals, clean-sheet truth, fantasy points, and Risk Play outcomes.

Useful API-Football references:

- [API-Football documentation](https://www.api-football.com/documentation-v3)
- [API-Football beginner guide](https://www.api-football.com/news/post/how-to-get-started-with-api-football-the-complete-beginners-guide)

## Rebuild Public Data

After refreshing `scoring/truth_data/latest_truth.json`, rebuild the public files:

```powershell
uv run python team_submission/build_public_context.py
```

The builder reads only local normalized truth and writes redacted public context.
It does not call API-Football and does not need an API key.
