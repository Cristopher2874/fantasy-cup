# Inno Fantasy Data

This folder is the backend runtime data area. The repository should only keep
small samples here; real generated files are local/deployment artifacts and are
ignored by Git.

## Tracked Samples

Use `samples/` as the contract reference for UI/auth integration and teammate
onboarding:

- `samples/public_data/` shows the public matchday files exposed by
  `/public-data`.
- `samples/source_of_truth/` shows the private post-match truth file used by the
  scorer.

The samples are intentionally small. They document shape and naming, not a full
World Cup matchday.

## Generated Folders

These folders are produced while the app runs and should not be committed:

| Folder | Produced by | Purpose |
| --- | --- | --- |
| `public_data/` | `services.daily_source_gen` | Latest public matchday bundle available to skills and UI. |
| `public_data/by_date/YYYY-MM-DD/` | `services.daily_source_gen` | Archived public bundles used by source-of-truth generation. |
| `source_of_truth/` | `services.daily_truth_gen` | Latest and archived post-match truth used by scoring. |
| `source/` | API clients | Raw API-Football cache/debug snapshots. |
| `runs/` | Upload pipeline | Per-upload skill snapshot, Codex logs, submissions, and per-run scoring copy. |
| `scores/` | Score engine | Leaderboard plus score result copies by job id. |

## Periodic Jobs

The game flow depends on two scheduled data jobs. Run them from the
`inno-fantasy` app root on a VM/container with `uv` and API credentials:

```bash
bash scripts/generate-game-data.sh public 2022-11-21
bash scripts/generate-game-data.sh truth 2022-11-21
```

Use these settings in deployment:

- `APISPORTS_KEY` or `API_FOOTBALL_KEY` for API-Football.
- `backend/config/config.yaml` for league, season, Codex runner, rate-limit,
  and scoring defaults.
- `REFRESH=1` to bypass cached API responses.

The scripts still accept `LEAGUE_ID` and `SEASON` as one-off overrides, but if
they are omitted the Python generators use `game.default_league_id` and
`game.default_season` from `config.yaml`.

Expected daily rhythm:

1. Morning public-data generation writes `public_data/`.
2. Users upload skills while the public bundle is available.
3. Night source-of-truth generation writes `source_of_truth/latest_truth.json`.
4. The score engine compares Codex submissions against the latest truth file.

## Public Data Contract

Public data is intentionally safe for user skills. It contains upcoming matches,
eligible players, prior stats, risk claim options, and a JSON answer template.
Skills should not receive `source_of_truth/`.

Important public files:

- `manifest.json`: generated timestamp, matchday id, source metadata, file list.
- `matchday.json`: game rules and limits for the matchday.
- `matches.json`: upcoming fixture list.
- `players.json`: eligible player records with `record_id` values.
- `risk_claims.json`: allowed risk claims per match.
- `answer_template.json`: expected Codex claim structure.

## Source Of Truth Contract

Source of truth is private backend data generated after matches finish. It is
used by `services.score_engine` and should only be exposed through score
results, not as public skill data.

Important truth fields:

- `matches`: final scores and normalized risk outcomes per fixture.
- `players`: actual player scoring records keyed by `record_id`.
- `capabilities`: claim types and scoring capabilities supported by the scorer.
- `state.complete`: whether all required matches were finished when generated.
