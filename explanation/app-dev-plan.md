# AI Agent Fantasy World Cup - App Dev Plan

## Purpose

This plan turns the game draft in `game_explanation.md` into a buildable app.
The app is not a normal fantasy football manager. It is a tournament platform
where teams submit AI agent Skills, the platform runs those Skills against
official matchday data, validates the structured answers, scores the results,
and publishes standings.

The build is split into two main phases:

1. Local development: no database. Store state as JSON files and make the full
   game loop playable on a laptop.
2. OCI production: move persistence, team memory, skill execution, and storage
   to OCI services, especially Oracle Database and hosted container execution.

The local phase should prove the rules and UX. The OCI phase should make the
same loop durable, isolated, auditable, and ready for real teams.

## Product Scope

### Core Loop

On each matchday:

1. Organizer imports or approves official matchday data.
2. App builds a tournament artifact bundle for that scoring window.
3. App snapshots each team's latest accepted Skill package.
4. App runs each team agent in isolation.
5. Agent returns structured answers:
   - `fantasy_xi`: exactly 11 eligible player IDs.
   - `risk_play`: one valid Risk Play claim, or `null`.
   - `strategy_summary`: short plain-text explanation.
   - `bracket`: knockout picks, only during the bracket lock window.
6. App validates answers against official schemas and IDs.
7. App scores real match events, Risk Play, and bracket predictions.
8. App publishes leaderboard, matchday results, and private team run history.

### Participants

| Participant | Needs |
| --- | --- |
| Teams | Register, submit Skills, see accepted snapshot, view private run history, learn why answers failed. |
| Organizers | Manage teams, cutoffs, data imports, agent runs, scoring reviews, and publishing. |
| Public viewers | See standings, matchday results, rules summary, and public data catalog. |

### Boundaries

The MVP should not include budgets, captains, transfer markets, manual daily
fantasy picks, or substitutions unless the final tournament guide adds them.

The final participant guide and official tournament artifacts are authoritative
when they conflict with this plan.

## Game Features To Implement

### Fantasy XI

The agent must select 11 eligible player IDs from official matchday data.

Draft validation rules:

| Position | Requirement |
| --- | --- |
| Goalkeeper | Exactly 1 |
| Defenders | 3 to 5 |
| Midfielders | 3 to 5 |
| Forwards | 1 to 3 |
| Total | Exactly 11 |

Draft scoring:

| Event | Points |
| --- | ---: |
| Player starts | +2 |
| Player plays 60+ minutes | +2 |
| Goal | +6 |
| Assist | +4 |
| Defender or goalkeeper clean sheet | +4 |
| Goalkeeper makes 3+ saves | +2 |
| Yellow card | -1 |
| Red card | -3 |
| Own goal | -3 |

### Risk Play

The agent may select one published claim or skip.

Stake is based on the team's points before the matchday:

| Category | Stake |
| --- | ---: |
| Green | 15% |
| Yellow | 25% |
| Red | 35% |

Correct claims add the stake. Incorrect claims subtract the stake. Scores can
go below zero.

### Bracket Play

Bracket picks are submitted once after the knockout bracket is known and before
the cutoff. Picks lock permanently.

Draft scoring:

| Prediction | Points |
| --- | ---: |
| Round of 32 winner | +5 |
| Round of 16 winner | +8 |
| Quarterfinal winner | +12 |
| Semifinal winner | +18 |
| Champion | +30 |

## Skill Package Model

Teams submit a ZIP or GitHub repo with this draft shape:

```text
my-team-skills/
  README.md
  skills/
    pick-fantasy-xi/
      SKILL.md
    choose-risk-play/
      SKILL.md
    explain-strategy/
      SKILL.md
    build-bracket/
      SKILL.md
```

Each direct child of `skills/` is one Skill. `SKILL.md` is required. Optional
folders include `references/`, `assets/`, `scripts/`, and `agents/`.

V1 should accept Markdown-only Skills. Script execution inside submitted
Skills should stay disabled until the sandbox policy is explicit and tested.

## Tournament Artifacts

Every agent run receives an official artifact bundle. These files are the only
source of truth for IDs, schemas, and hidden matchday values during execution.

```text
tournament/
  rules.md
  answer-formats/
    fantasy-xi.schema.json
    risk-play.schema.json
    strategy-summary.schema.json
    bracket.schema.json
  data/
    matchday.json
    teams.json
    players.json
    matches.json
    risk-claims.json
    standings.json
```

The public app can show schema and field descriptions. It should not expose
hidden matchday values, other teams' private Skills, or private agent outputs.

## Recommended Agent Execution Strategy

Use a runner interface so local and OCI execution can evolve independently:

```text
AgentRunner
  MockAgentRunner         local deterministic dev runner
  HostedContainerRunner  OCI/OpenAI-compatible Responses API + Shell Tool
  CodexCliRunner         optional local experiment only
```

### Primary Recommendation

Use OCI GenAI/OpenAI-compatible hosted containers with the Shell Tool for the
real autonomous process. This matches the samples in this repo better than an
auto-triggered local Codex CLI loop.

Relevant samples are stored in `explanation/samples/` in this repo:

| Sample | Use In This App |
| --- | --- |
| `samples/sample_container_use.py` | Package an inline Skill, create a hosted container, attach Skill, run Shell Tool. |
| `samples/sample_shell.py` | Ask the agent to write files under `/mnt/data`, list generated files, retrieve artifacts. |
| `samples/sample_skill_cli_usage.py` | Use hosted Skill references instead of inline ZIP Skills when available. |
| `samples/vector_store.py` | Search team memory or official knowledge using vector stores. |
| `samples/api_sports_sample.py` | Starting point for API-Sports football API access. |

### Codex CLI Note

Codex CLI can be useful for local experiments if it supports a stable
non-interactive command in the target environment. For production, prefer the
API-driven container runner because it can be invoked by a backend job,
scheduled task, or queue worker without relying on a desktop session.

## Phase 1 - Local Development With JSON Storage

### Goal

Build the complete game loop locally with no database. State is stored as JSON
and files under `data/`. The app can run with a mock agent first, then switch to
the hosted container runner while still using JSON persistence.

### Local Stack

| Layer | Choice |
| --- | --- |
| Backend | FastAPI |
| Frontend | Simple static HTML/JS served by FastAPI, or React if the UI grows |
| Persistence | JSON files and folders under `data/` |
| Agent runner | Mock runner first, hosted container runner behind a feature flag |
| Football data | API-Sports adapter based on `samples/api_sports_sample.py`, with cached raw responses |
| Validation | `jsonschema` or Pydantic models |
| Scheduling | Manual organizer trigger, then local scheduled command |

### Local Folder Structure

```text
fantasy-cup/
  backend/
    main.py
    config.py
    routes/
      public.py
      teams.py
      organizer.py
    services/
      state_store.py
      package_validator.py
      artifact_builder.py
      answer_validator.py
      scorer.py
      risk_resolver.py
      bracket_resolver.py
      leaderboard.py
    runners/
      base.py
      mock_runner.py
      hosted_container_runner.py
      codex_cli_runner.py
    integrations/
      football_api.py
  frontend/
    index.html
    app.js
    styles.css
  data/
    state/
      teams.json
      submissions.json
      snapshots.json
      matchdays.json
      runs.json
      leaderboard.json
    source/
      api-sports/
    uploads/
      TGR-001/
    snapshots/
      TGR-001/
    artifacts/
      MD-001/
        tournament/
    runs/
      MD-001/
        TGR-001/
          prompt.txt
          answers.json
          strategy_summary.txt
          raw_response.json
          validation.json
          scoring.json
          logs.txt
  schemas/
    fantasy-xi.schema.json
    risk-play.schema.json
    strategy-summary.schema.json
    bracket.schema.json
  explanation/
    game_explanation.md
    app-dev-plan.md
    samples/
      api_sports_sample.py
      sample_container_use.py
      sample_shell.py
      sample_skill_cli_usage.py
      vector_store.py
```

### JSON State Files

`teams.json`

```json
[
  {
    "id": "TGR-001",
    "name": "The Golden Robots",
    "members": ["Name One", "Name Two"],
    "token_hash": "local-dev-hash",
    "submission_method": "zip",
    "repo_url": null,
    "created_at": "2026-05-25T00:00:00Z"
  }
]
```

`snapshots.json`

```json
[
  {
    "id": "SNP-001",
    "team_id": "TGR-001",
    "matchday_id": "MD-001",
    "source": "zip",
    "path": "data/snapshots/TGR-001/SNP-001",
    "accepted": true,
    "errors": [],
    "created_at": "2026-05-25T00:00:00Z"
  }
]
```

`runs.json`

```json
[
  {
    "id": "RUN-001",
    "team_id": "TGR-001",
    "matchday_id": "MD-001",
    "snapshot_id": "SNP-001",
    "status": "scored",
    "runner": "mock",
    "fantasy_points": 42,
    "risk_points": 6.3,
    "bracket_points": 0,
    "total_points": 48.3,
    "strategy_summary": "Focused on starters with favorable clean-sheet odds.",
    "artifact_path": "data/runs/MD-001/TGR-001",
    "created_at": "2026-05-25T00:00:00Z"
  }
]
```

### Local API Routes

Public:

```text
GET  /api/leaderboard
GET  /api/matchdays
GET  /api/matchdays/{matchday_id}/results
GET  /api/catalog
```

Team:

```text
POST /api/teams/register
POST /api/team/login
GET  /api/team/me
POST /api/team/submission/zip
POST /api/team/submission/repo
GET  /api/team/submissions
GET  /api/team/runs
GET  /api/team/runs/{run_id}
```

Organizer:

```text
POST /api/org/matchdays
POST /api/org/matchdays/{matchday_id}/import-football-data
POST /api/org/matchdays/{matchday_id}/build-artifacts
POST /api/org/matchdays/{matchday_id}/run
POST /api/org/matchdays/{matchday_id}/score
POST /api/org/matchdays/{matchday_id}/publish
GET  /api/org/runs/{run_id}/logs
```

### Football API Adapter

`samples/api_sports_sample.py` demonstrates the API-Sports host and auth header:

```python
conn = http.client.HTTPSConnection("v3.football.api-sports.io")
headers = {"x-apisports-key": "..."}
conn.request("GET", "/leagues", headers=headers)
```

Turn this into `backend/integrations/football_api.py`.

Local responsibilities:

1. Read `APISPORTS_KEY`, `APISPORTS_LEAGUE_ID`, `APISPORTS_SEASON`, and
   optional `APISPORTS_TIMEZONE` from config.
2. Fetch fixtures, teams, players, lineups, events, and statistics needed for
   scoring.
3. Save raw API responses to `data/source/api-sports/`.
4. Normalize provider data into official tournament files.
5. Let the organizer review and patch normalized data before publishing.

### Local Runner Flow

For each team and matchday:

1. Validate and snapshot the latest package.
2. Build `tournament/` artifact bundle.
3. Create a run folder under `data/runs/{matchday_id}/{team_id}/`.
4. Generate a single prompt that instructs the model to:
   - Use the submitted Skills.
   - Read the official tournament files.
   - Write `/mnt/data/answers.json`.
   - Write `/mnt/data/strategy_summary.txt`.
   - Return no private data beyond the requested output.
5. Run through `MockAgentRunner` or `HostedContainerRunner`.
6. Validate generated `answers.json`.
7. Score valid pieces and apply fallback policy for invalid pieces.
8. Persist raw response, validation, scoring, and summary files.

### Local Hosted Container Runner

Use the pattern from `samples/sample_container_use.py` and `samples/sample_shell.py`:

1. Package the team's `skills/` folder as an inline Skill ZIP, or reference a
   hosted Skill ID if the Skill has already been uploaded.
2. Create a hosted container with:
   - short expiration
   - memory limit
   - network disabled by default
   - optional allowlist only for approved domains
3. Attach official tournament files to the container workspace.
4. Call `client.responses.create(...)` with the Shell Tool and container
   reference.
5. Retrieve `/mnt/data/answers.json` and other generated files through the
   container files API.
6. Delete the container unless running in debug mode.

### Local Data Catalog

The public catalog shows fields, types, descriptions, and answer schemas. It
does not show hidden values for players, claims, or private team data.

Catalog entities:

| Entity | Visible |
| --- | --- |
| Players | field names, types, position rules |
| Matches | field names, kickoff, teams when public |
| Risk claims | claim schema and category meanings |
| Standings | public scores and ranks |
| Answer schemas | required JSON shapes |

### Local UI

Build the actual game hub, not a landing page.

Required screens:

| Screen | Purpose |
| --- | --- |
| Home | Current standings, next matchday status, latest published results. |
| Leaderboard | Rank, team, total points, fantasy points, risk record, bracket points. |
| Matchday Results | Team answers, player points, risk outcome, strategy summary. |
| Data Catalog | Schema browser and field descriptions. |
| Team Dashboard | Submission status, accepted snapshot, run history, errors, strategy summaries. |
| Team Upload | ZIP upload or GitHub URL. |
| Organizer Console | Import data, build artifacts, run agents, score, publish. |

### Phase 1 Milestones

1. Project scaffold:
   - FastAPI app
   - static frontend shell
   - JSON state store
   - local config
2. Team and submission flow:
   - team registration
   - token login
   - ZIP upload
   - GitHub URL registration
   - Skill package validation
3. Artifact and schema flow:
   - answer schemas
   - matchday artifact builder
   - public data catalog
4. Mock game loop:
   - mock football data
   - mock agent runner
   - validation
   - fantasy scoring
   - leaderboard
5. Real football data adapter:
   - API-Sports wrapper from `samples/api_sports_sample.py`
   - raw response cache
   - normalized matchday files
   - organizer review patches
6. Hosted agent execution:
   - inline Skill packaging from sample container flow
   - Shell Tool artifact generation
   - container file retrieval
   - cleanup and debug mode
7. Risk and bracket:
   - Risk Play validation and stake scoring
   - bracket lock and bracket scoring
8. End-to-end local demo:
   - at least two sample teams
   - one matchday run
   - one published leaderboard
   - run logs visible to organizer

## Phase 2 - OCI, Oracle Database, And Team Memory

### Goal

Move from local JSON to durable OCI services while keeping the same app
behavior. The production system should support real team submissions,
isolated agent runs, audit history, private team memory, and reliable scoring.

### OCI Service Map

| Need | OCI Service |
| --- | --- |
| Relational game state | Oracle Autonomous Database or Oracle Database |
| JSON run payloads | Oracle Database JSON columns |
| Team memory search | OCI GenAI/OpenAI vector stores and/or Oracle AI Vector Search |
| Large files | OCI Object Storage |
| Agent sandbox | OCI GenAI/OpenAI-compatible hosted containers with Shell Tool |
| Backend hosting | OCI Compute, Container Instances, or OKE |
| Scheduled runs | OCI Scheduler, cron on Compute, or queue-triggered worker |
| Secrets | OCI Vault |
| Logs and metrics | OCI Logging and Monitoring |
| Public delivery | Load Balancer plus HTTPS |

### Oracle Database Model

Use relational tables for canonical state and JSON columns for generated
payloads. Keep Object Storage paths for large artifacts.

`teams`

```text
id              VARCHAR2 PRIMARY KEY
name            VARCHAR2 NOT NULL
token_hash      VARCHAR2 NOT NULL
members_json    JSON
submission_type VARCHAR2
repo_url        VARCHAR2
created_at      TIMESTAMP
```

`skill_snapshots`

```text
id              VARCHAR2 PRIMARY KEY
team_id         VARCHAR2 REFERENCES teams(id)
matchday_id     VARCHAR2
source_type     VARCHAR2
source_ref      VARCHAR2
object_uri      VARCHAR2
commit_hash     VARCHAR2
accepted        NUMBER(1)
validation_json JSON
created_at      TIMESTAMP
```

`matchdays`

```text
id              VARCHAR2 PRIMARY KEY
match_date      DATE
stage           VARCHAR2
status          VARCHAR2
artifact_uri    VARCHAR2
provider_json   JSON
created_at      TIMESTAMP
```

`runs`

```text
id                  VARCHAR2 PRIMARY KEY
team_id             VARCHAR2 REFERENCES teams(id)
matchday_id         VARCHAR2 REFERENCES matchdays(id)
snapshot_id         VARCHAR2 REFERENCES skill_snapshots(id)
runner_type         VARCHAR2
container_id        VARCHAR2
status              VARCHAR2
answers_json        JSON
validation_json     JSON
scoring_json        JSON
strategy_summary    CLOB
fantasy_points      NUMBER
risk_points         NUMBER
bracket_points      NUMBER
total_points        NUMBER
artifact_uri        VARCHAR2
created_at          TIMESTAMP
```

`risk_claim_results`

```text
id              VARCHAR2 PRIMARY KEY
run_id          VARCHAR2 REFERENCES runs(id)
claim_id        VARCHAR2
category        VARCHAR2
stake_points    NUMBER
outcome         VARCHAR2
points_earned   NUMBER
details_json    JSON
```

`team_memory_items`

```text
id              VARCHAR2 PRIMARY KEY
team_id         VARCHAR2 REFERENCES teams(id)
source_type     VARCHAR2
source_id       VARCHAR2
visibility      VARCHAR2
content_text    CLOB
metadata_json   JSON
vector_ref      VARCHAR2
created_at      TIMESTAMP
```

### Team Memory

Team memory should help an agent learn from its own prior behavior without
leaking other teams' private data.

Memory sources:

| Source | Visibility |
| --- | --- |
| Team's prior strategy summaries | private to team |
| Team's prior valid answers | private to team |
| Team's validation errors | private to team |
| Public rules and scoring docs | shared |
| Published matchday results | shared |

Do not store hidden future matchday values in reusable memory. Do not allow one
team's private Skill, prompt, or generated output to appear in another team's
retrieval context.

Implementation options:

1. Use OCI GenAI/OpenAI vector stores like `samples/vector_store.py`.
2. Use Oracle Database with vector columns if Oracle AI Vector Search is
   enabled in the chosen database.
3. Start with vector stores for speed, then mirror metadata in Oracle Database.

Runner retrieval flow:

1. Build a query from matchday context and the team's previous error patterns.
2. Search shared rules memory and that team's private memory.
3. Inject only the top relevant snippets into the run prompt.
4. Save the new strategy summary, validation result, and scoring notes back to
   team memory after the run is scored.

### OCI Agent Execution Flow

1. Worker receives `RunMatchday(matchday_id)`.
2. Worker reads teams and accepted snapshots from Oracle Database.
3. Worker downloads official artifacts and team snapshot from Object Storage.
4. Worker creates one hosted container per team run.
5. Worker attaches inline Skill ZIP or hosted Skill references.
6. Worker keeps network disabled unless the tournament explicitly allows
   outbound research domains.
7. Worker asks the Shell Tool to generate `/mnt/data/answers.json` and
   `/mnt/data/strategy_summary.txt`.
8. Worker retrieves files through the container files API.
9. Worker stores raw artifacts in Object Storage.
10. Worker validates and scores outputs.
11. Worker writes canonical results to Oracle Database.
12. Worker deletes or expires the hosted container.

### Object Storage Layout

```text
oci://fantasy-cup/
  submissions/
    TGR-001/
      original/
      snapshots/
  matchdays/
    MD-001/
      tournament.zip
      provider-raw/
      normalized/
  runs/
    MD-001/
      TGR-001/
        prompt.txt
        raw_response.json
        answers.json
        strategy_summary.txt
        validation.json
        scoring.json
        logs.txt
```

### Production Security

1. Store API-Sports keys, OCI credentials, JWT signing keys, and org password
   material in OCI Vault.
2. Hash team tokens. Never store plaintext tokens.
3. Disable hosted container network by default.
4. If network is required, use allowlisted domains and no team-provided
   secrets.
5. Scan ZIP packages for size, path traversal, unexpected binaries, and secret
   patterns.
6. Keep submitted Skills immutable once snapshotted for a matchday.
7. Keep raw run artifacts private to organizers and the owning team.
8. Publish only validated answers, scoring summaries, and public standings.

### Phase 2 Milestones

1. Database migration:
   - Oracle schema
   - repository layer replacing JSON state store
   - migration/import from local JSON files
2. Object Storage migration:
   - store submissions, snapshots, artifacts, run outputs
   - signed/internal access for backend only
3. OCI runner hardening:
   - hosted container lifecycle
   - inline and hosted Skill paths
   - artifact retrieval
   - retry and timeout policy
4. Team memory:
   - vector store or Oracle vector search
   - strict team partitioning
   - memory writeback after scoring
5. Production scheduling:
   - scheduled matchday job
   - manual organizer override
   - run status dashboard
6. Observability:
   - structured logs
   - per-team run trace
   - scoring audit view
7. Deployment:
   - backend on OCI
   - HTTPS
   - environment config
   - smoke test with sample teams

## Validation And Failure Policy

Apply validation independently per answer section:

| Failure | MVP Behavior |
| --- | --- |
| Skill package cannot refresh | Use latest accepted snapshot if available. |
| Fantasy XI missing or invalid | Reuse latest valid Fantasy XI only if still legal; otherwise score 0 for Fantasy XI. |
| Risk Play missing or invalid | Treat as skipped Risk Play. Do not reuse prior Risk Play. |
| Strategy summary missing | Mark as warning, not a scoring failure. |
| Bracket submitted after lock | Reject bracket answer. |
| Provider data ambiguous | Organizer review required before publishing. |
| Runner timeout | Mark run failed and preserve logs. |

## Build Order Summary

Phase 1 should end with a fun, usable local game that proves the tournament.
Phase 2 should harden the exact same loop on OCI.

```text
Phase 1: Local JSON MVP
  [ ] Scaffold FastAPI, static UI, JSON state store
  [ ] Register/login teams and organizer
  [ ] Accept ZIP and repo submissions
  [ ] Validate Skill package shape
  [ ] Build official tournament artifacts
  [ ] Implement mock runner
  [ ] Implement answer validation
  [ ] Implement Fantasy XI scoring
  [ ] Implement leaderboard and team dashboard
  [ ] Wrap API-Sports football API from samples/api_sports_sample.py
  [ ] Implement hosted container runner from samples
  [ ] Add Risk Play scoring
  [ ] Add Bracket Play lock and scoring
  [ ] Demo with two sample teams

Phase 2: OCI Production
  [ ] Create Oracle Database schema
  [ ] Replace JSON state store with repository layer
  [ ] Move large files to OCI Object Storage
  [ ] Use OCI Vault for secrets
  [ ] Run agents in hosted containers with Shell Tool
  [ ] Add vector store or Oracle vector team memory
  [ ] Add scheduled autonomous matchday runs
  [ ] Add audit logs and organizer review screens
  [ ] Deploy backend and frontend on OCI
  [ ] Run end-to-end production smoke test
```

## Immediate Next Implementation Slice

Start with the smallest playable path:

1. Define schemas for `fantasy_xi`, `risk_play`, and `strategy_summary`.
2. Create `StateStore` that reads and writes JSON under `data/state/`.
3. Add organizer endpoint to create a mock matchday.
4. Add team ZIP upload and package validation.
5. Add `MockAgentRunner` that writes a valid `answers.json`.
6. Add answer validation and Fantasy XI scoring against mock data.
7. Render leaderboard and matchday results.

Once that is fun locally, wire the hosted container runner using the sample
container, shell, and Skill patterns already in this repo.
