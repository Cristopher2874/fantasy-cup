# Fantasy Cup Playtest App

This is a standalone local UI for generating team submission JSON from the fixed 2022 World Cup truth file.

## Run

From the project root:

```powershell
.\.venv\Scripts\python.exe scoring\daily_truth_pipeline.py
.\.venv\Scripts\python.exe playtest_app\server.py
```

Open:

```text
http://127.0.0.1:8765
```

## Data Files

- `playtest_app/data/team_submissions.json`: saved team payloads.
- `playtest_app/data/leaderboard_seed.json`: starting points before the playtest matchday.
- `playtest_app/data/matchday_results.json`: generated scoring results.
- `playtest_app/data/leaderboard.json`: generated leaderboard after scoring.

The app reads truth from `scoring/truth_data/latest_truth.json` and uses `scoring/team_claims_scorer.py` for the same scoring rules as the standalone pipeline.

For public playtests, the server assigns every team a fixed 100-point starting score. The UI does not expose reset controls, and the server rotates the local JSON batch when a new registration would exceed 59 teams.
