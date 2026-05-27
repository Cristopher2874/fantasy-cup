# API-Football Capability Review

This note checks whether API-Football can supply the football data required by
`explanation/game_explanation.md`.

## Short Verdict

API-Football is a good fit for the current app requirements, with one important
condition: the project will need paid-plan access for the active World Cup 2026
season. The configured key in this workspace currently behaves like a Free plan
key and rejects `league=1&season=2026`.

The API covers the core football inputs needed for the game:

- teams and national-team IDs
- player IDs, names, teams, and positions
- fixtures, rounds, scores, status, extra time, and penalties
- standings
- lineups and starters
- match events: goals, own goals, cards, substitutions
- player match statistics: minutes, goals, assists, cards, goalkeeper saves

The app still needs to create and own the game-specific layer:

- eligible player list rules
- official tournament artifacts
- Risk Play claim generation
- Fantasy XI validation rules
- Fantasy XI scoring rules
- bracket submission locks
- organizer review and patch workflow

## Sources Checked

- [API-Football pricing](https://www.api-football.com/pricing)
- [API-Football coverage](https://www.api-football.com/coverage)
- [API-Football beginner guide](https://www.api-football.com/news/post/how-to-get-started-with-api-football-the-complete-beginners-guide)
- [API-Football World Cup 2026 guide](https://www.api-football.com/news/post/fifa-world-cup-2026-guide-to-using-data-with-api-sports)
- Local probes using the configured `APISPORTS_KEY`, without printing the key.

## Local Probe Findings

The configured key returned this when checking World Cup 2026:

```text
GET /leagues?id=1&season=2026
Free plans do not have access to this season, try from 2022 to 2024.
```

For World Cup 2022, the API returned coverage flags that are directly relevant
to the game:

```text
fixtures.events = true
fixtures.lineups = true
fixtures.statistics_fixtures = true
fixtures.statistics_players = true
players = true
predictions = true
standings = true
injuries = false
odds = false
```

I also verified real historical response shape:

- `GET /fixtures?league=1&season=2022` returned 64 World Cup fixtures.
- `GET /fixtures?id=855735` returned events, lineups, team statistics, and player statistics.
- Player statistics included minutes, position, substitute flag, goals, assists, cards, and goalkeeper saves.
- `GET /fixtures?id=855767` included a goal event with `detail = "Own Goal"`.

## Requirement Matrix

| App Requirement | API-Football Endpoint | Fit | Notes |
| --- | --- | --- | --- |
| World Cup competition setup | `/leagues?id=1&season=YYYY` | Good | Use this first to confirm season coverage flags. Free plan blocked 2026 in this workspace. |
| National teams | `/teams?league=1&season=YYYY` | Good | Returns stable team IDs, names, codes, logos, and national-team flag. |
| Player IDs and positions | `/players?league=1&season=YYYY&page=N` | Good | Results are paginated at 20 players per page. Normalize API positions into `GK`, `DEF`, `MID`, `FWD`. |
| Eligible player list | `/players`, plus organizer rules | Partial | API gives the pool; the app must decide who is eligible for each matchday. |
| Match schedule | `/fixtures?league=1&season=YYYY`, `/fixtures/rounds` | Good | Use rounds for group/knockout organization and fixture lists for matchday windows. |
| Starters | `/fixtures?id=FIXTURE_ID` or `/fixtures/lineups?fixture=FIXTURE_ID` | Good, time-sensitive | Lineups are typically available close to kickoff; some competitions may expose them later. |
| Player started scoring | lineups or `/fixtures/players` | Good | `games.substitute = false` plus minutes is enough for the app's +2 starts rule. |
| 60+ minutes scoring | `/fixtures/players?fixture=FIXTURE_ID` | Good | `statistics[].games.minutes` directly supports this. |
| Goals | `/fixtures/players`, `/fixtures/events` | Good | Prefer player stats for fantasy points; use events for timeline and Risk Play. |
| Assists | `/fixtures/players`, `/fixtures/events` | Good | Player stats include assists; events include assist player on goal events. |
| Yellow/red cards | `/fixtures/players`, `/fixtures/events` | Good | Use player stats for Fantasy XI scoring and events for match-level Risk Play. |
| Own goals | `/fixtures/events` | Good | Own goals appear as `type = "Goal"` and `detail = "Own Goal"`. |
| Goalkeeper saves | `/fixtures/players`, `/fixtures/statistics` | Good | Individual saves are available under player match statistics. |
| Clean sheets | final score plus player position/minutes | Good with rule choice | The API does not emit a direct fantasy clean-sheet flag. Derive from team goals conceded and your eligibility rule. |
| Match has 2+ goals | `/fixtures` score | Good | Directly derivable from final score. |
| No goal in opening 10 minutes | `/fixtures/events` | Good | Use goal events and `time.elapsed` / `time.extra`. |
| Both teams score | `/fixtures` score | Good | Directly derivable from final score. |
| Selected team scores first | `/fixtures/events` | Good | First goal event determines it; handle own goals explicitly. |
| Selected player scores | `/fixtures/events`, `/fixtures/players` | Good | Use events if own-goal distinction matters. |
| Exact final score | `/fixtures.score.fulltime` | Good | For knockout matches, decide whether risk uses fulltime, after-extra-time, or penalty result. |
| Player scores 2+ | `/fixtures/players`, `/fixtures/events` | Good | Prefer events if own goals must be excluded. |
| Red card shown | `/fixtures/events` | Good | Look for red-card details, including second-yellow red if your rules count it. |
| Extra time | fixture status/score | Good | `status.short = AET` or extra-time score fields indicate this. |
| Penalties | fixture status/score | Good | `status.short = PEN` and `score.penalty` support this. |
| Group standings | `/standings?league=1&season=YYYY` | Good | World Cup 2026 guide says this returns all group tables. |
| Bracket resolution | `/fixtures/rounds`, `/fixtures` | Good | API can resolve winners; the app owns prediction locking and scoring. |

## Main Risks

### 1. Plan Access

Pricing says all plans include all competitions and endpoints, but Free plans
are season-limited. The local probe confirmed this matters: the current key
cannot access World Cup 2026. For this app, assume at least Pro access is needed.

### 2. Coverage Can Vary

The coverage page says detailed coverage may vary by season or fixture. The app
should check `/leagues?id=1&season=2026` at startup/import time and refuse to
publish official artifacts until required coverage flags are present.

Required flags for this game:

```text
fixtures.events
fixtures.lineups
fixtures.statistics_players
players
standings
```

Useful but not required:

```text
fixtures.statistics_fixtures
predictions
injuries
odds
```

### 3. Lineup Timing

Lineups usually arrive shortly before kickoff, and in some competitions may
arrive only after the match. That is fine for the current game if agents pick
from an eligible player pool before games and non-playing selected players score
zero. Do not design V1 around knowing confirmed starters before the agent run.

### 4. Clean Sheet Rule

API-Football gives final scores, goal events, lineups, and minutes. It does not
provide a fantasy-specific clean-sheet flag. The safest V1 rule is:

```text
GK/DEF earns clean-sheet points when:
- player played at least 60 minutes
- player's team conceded 0 goals in the match
```

If the final rules require "while the player was on the pitch", the app must
derive player on/off intervals from lineups and substitution events, then compare
them to opponent goal timings.

### 5. Risk Play Is App-Owned

The API can resolve every example Risk Play listed in `game_explanation.md`, but
it does not generate game-ready claims. The app should generate `risk-claims.json`
from fixture/player/team data and organizer-configured templates.

### 6. Request Budget

The Free plan has 100 requests/day. Pricing currently lists Pro at 7,500/day,
Ultra at 75,000/day, and Mega at 150,000/day. Pro should be enough for a
tournament importer if the app caches raw responses and fetches fixture details
in batches.

## Recommended Import Strategy

1. Call `/leagues?id=1&season=2026` and validate required coverage flags.
2. Call `/teams?league=1&season=2026`.
3. Fetch `/players?league=1&season=2026&page=N` until `paging.current == paging.total`.
4. Call `/fixtures/rounds?league=1&season=2026`.
5. Call `/fixtures?league=1&season=2026` for schedule and fixture IDs.
6. For completed or active matches, fetch details with `/fixtures?ids=ID1-ID2-...` in chunks of up to 20 fixture IDs.
7. Normalize into:
   - `teams.json`
   - `players.json`
   - `matches.json`
   - `standings.json`
   - `risk-claims.json`
8. Keep all raw API responses under `data/source/api-sports/` for audit.
9. Let organizers review normalized data before building official artifacts.

## Build Recommendation

The current architecture already has the right boundary:

```text
backend/integrations/football_api.py  -> raw API client
backend/services/artifact_builder.py  -> official tournament files
backend/services/scorer.py            -> game-specific scoring
```

Add a normalization layer between the raw API client and the artifact builder:

```text
backend/services/football_importer.py
backend/services/football_normalizer.py
```

The importer should fetch/cache provider responses. The normalizer should turn
API-Football shapes into the app's stable internal shapes, so the scorer and
agent artifacts are insulated from provider quirks.
