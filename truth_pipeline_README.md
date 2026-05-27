# Standalone Truth Pipeline

This pipeline is a local prototype for building the official scoring source of
truth from API-Football responses. It intentionally does not import anything
from the app folder.

The split is:

```text
daily_truth_pipeline.py  fetches API-Football data and writes JSON files
truth_parser.py          parses raw fixture payloads into normalized truth
team_claims_scorer.py    validates and scores team choices in memory
score_team_claims.py     reads/writes JSON files and calls TeamClaimsScorer
```

## Run

Add your key to `.env`:

```env
APISPORTS_KEY=your_api_key_here
```

Then run:

```powershell
uv run daily_truth_pipeline.py
```

The script writes:

```text
truth_data/
  raw/<run_id>/api_football_raw.json
  final/<matchday_id>.truth.json
  latest_truth.json
```

## Configure

Edit the constants at the top of `daily_truth_pipeline.py`.

For Free-plan testing:

```python
SEASON = "2022"
SOURCE_MODE = "fixture_ids"
FIXTURE_IDS = ["855735", "855767", "977345", "978088", "979139"]
```

For a real daily run after matches:

```python
SEASON = "2026"
SOURCE_MODE = "date"
TARGET_DATE = "2026-06-11"
```

`SOURCE_MODE = "date"` first fetches fixtures for that date, then fetches each
fixture by individual `id` so the parser gets events, lineups, and player
statistics.

## What The Truth JSON Contains

The normalized truth file contains:

- point rules for Fantasy XI scoring
- API-supported Fantasy XI event fields
- API-supported Risk Play claim fields
- one normalized match record per fixture
- one normalized player record per player with API match statistics
- precomputed player fantasy points
- precomputed match-level and parameterized Risk Play truth values

The app still owns:

- each team's Fantasy XI choices
- each team's Risk Play selection
- team score before matchday
- stake calculation
- organizer review overrides
- bracket pick locking

## API-Football Free-Plan Notes

The current Free-plan key can access historical World Cup 2022 fixture details
by individual `id`. The `next`, `last`, old `date`, and batch `ids` fixture
filters may be blocked on Free plans.

The default fixture IDs exercise useful scoring cases:

| Fixture ID | Match | Useful For |
| --- | --- | --- |
| `855735` | England 6-2 Iran | goals, assists, cards, starters, minutes |
| `855767` | Canada 1-2 Morocco | own goal |
| `977345` | Morocco 0-0 Spain | clean sheets, extra time, penalties |
| `978088` | Morocco 1-0 Portugal | clean sheet, goalkeeper saves |
| `979139` | Argentina 3-3 France | final, extra time, penalties |

## Score Mock Team Claims

After `truth_data/latest_truth.json` exists, run:

```powershell
uv run score_team_claims.py
```

Inputs:

```text
mock_team_claims_2022.json
mock_leaderboard_2022.json
truth_data/latest_truth.json
```

Outputs:

```text
score_data/matchday_results.json
score_data/leaderboard.json
```

The mock claims use player `record_id` values such as `979139:278`, where the
first part is the match ID and the second part is the API-Football player ID.
The scorer also accepts `{ "match_id": "...", "player_id": "..." }` objects.
