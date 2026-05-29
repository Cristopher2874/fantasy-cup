# Public Data Catalog

Matchday ID: `truth-test-world-cup-2022`

## Files

- `matchday.json`: rules, scoring values, fixture IDs, and hidden-data policy.
- `matches.json`: one record per fixture available for this simulated matchday.
- `teams.json`: stable team IDs and per-fixture opponent context.
- `players.json`: eligible player records; submit `record_id` values in Fantasy XI.
- `risk_claims.json`: allowed Risk Play claim types and match-specific claim options.
- `answer_template.json`: minimal single-team answer shape.

## Match Scope

- `855735`: England vs Iran (Group Stage - 1, 2022-11-21T13:00:00+00:00)
- `855767`: Canada vs Morocco (Group Stage - 3, 2022-12-01T15:00:00+00:00)
- `976534`: England vs Senegal (Round of 16, 2022-12-04T19:00:00+00:00)
- `977345`: Morocco vs Spain (Round of 16, 2022-12-06T15:00:00+00:00)
- `978088`: Morocco vs Portugal (Quarter-finals, 2022-12-10T15:00:00+00:00)
- `979139`: Argentina vs France (Final, 2022-12-18T15:00:00+00:00)

## Player Eligibility

`players.json` currently contains 299 match-specific player records.
A `record_id` combines `match_id:player_id` so the scorer can disambiguate players
who appear in more than one test fixture.

Position limits:

- `GK`: 1 to 1 (Goalkeeper)
- `DEF`: 3 to 5 (Defender)
- `MID`: 3 to 5 (Midfielder)
- `FWD`: 1 to 3 (Forward)

## Risk Play

`risk_claims.json` contains 17 claim types and 98 match-specific claim options.
A team may submit one Risk Play object or `null`.

## Hidden Until Scoring

- fixture status and final score
- lineups and starters
- event timeline
- player minutes
- goals, assists, cards, saves, own goals, and clean-sheet truth
- fantasy points and point breakdowns
- risk claim outcomes and evidence

## Teams In Scope

- `26`: Argentina (matches: 979139)
- `5529`: Canada (matches: 855767)
- `10`: England (matches: 855735, 976534)
- `2`: France (matches: 979139)
- `22`: Iran (matches: 855735)
- `31`: Morocco (matches: 855767, 977345, 978088)
- `27`: Portugal (matches: 978088)
- `13`: Senegal (matches: 976534)
- `9`: Spain (matches: 977345)
