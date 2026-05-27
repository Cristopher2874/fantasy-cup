# AI Agent Fantasy World Cup - App System Diagrams

This document explains how the app should work from the local POC through the final production version. It is written for team alignment: product, engineering, organizers, and future contributors should be able to understand the full loop without reading the code first.

## 1. Product Context

The app is a tournament operations hub. Teams do not manually pick fantasy players every day. Instead, they submit AI agent Skills. The platform runs those Skills against official matchday artifacts, validates the agent output, scores the result, and publishes standings.

```mermaid
flowchart LR
  Team["Team<br/>Registers, submits Skills, reviews private runs"]
  Organizer["Organizer<br/>Approves data, triggers runs, reviews scoring"]
  Public["Public Viewer<br/>Views standings and published results"]

  App["Fantasy Cup App<br/>Tournament hub"]

  Team -->|"Register team<br/>Upload ZIP or repo URL<br/>View team dashboard"| App
  Organizer -->|"Create matchday<br/>Import/approve data<br/>Run agents<br/>Publish results"| App
  Public -->|"View leaderboard<br/>View matchday results<br/>View data catalog"| App

  App -->|"Official player IDs<br/>Matches<br/>Risk claims<br/>Answer schemas"| Artifacts["Tournament Artifacts"]
  App -->|"Run each team's accepted Skill"| Runner["Agent Runner"]
  Runner -->|"answers.json<br/>strategy_summary.txt"| App
  App -->|"Validated answers<br/>Scoring records<br/>Leaderboard totals"| Results["Published Results"]

  Results --> Public
  Results --> Team
  Results --> Organizer
```

## 2. Phase 1 Local POC Architecture

Phase 1 proves the game loop on a laptop. It avoids database, cloud storage, queue workers, real hosted containers, and real football provider calls unless explicitly enabled later.

```mermaid
flowchart TB
  Browser["Browser<br/>Static HTML, CSS, JS"]

  subgraph FastAPI["FastAPI Backend"]
    PublicRoutes["Public routes<br/>/api/leaderboard<br/>/api/matchdays<br/>/api/catalog"]
    TeamRoutes["Team routes<br/>register, login, upload ZIP, repo URL, runs"]
    OrgRoutes["Organizer routes<br/>seed demo, create matchday, build artifacts, run agents, publish"]
    Services["Services<br/>StateStore, package validator, artifact builder, answer validator, scorer, leaderboard"]
    MockRunner["MockAgentRunner<br/>Deterministic local agent output"]
  end

  subgraph LocalFiles["Local Files"]
    JSONState["data/state/*.json<br/>teams, submissions, snapshots, matchdays, runs, leaderboard"]
    Uploads["data/uploads/<team_id>/<submission>.zip"]
    Snapshots["data/snapshots/<team_id>/<snapshot_id>/skills/..."]
    Artifacts["data/artifacts/<matchday_id>/tournament/..."]
    Runs["data/runs/<matchday_id>/<team_id>/<run_id>/..."]
    Schemas["schemas/*.schema.json"]
  end

  Browser -->|"fetch()"| PublicRoutes
  Browser -->|"fetch() with team token"| TeamRoutes
  Browser -->|"organizer actions"| OrgRoutes

  PublicRoutes --> Services
  TeamRoutes --> Services
  OrgRoutes --> Services

  Services --> JSONState
  Services --> Uploads
  Services --> Snapshots
  Services --> Artifacts
  Services --> Runs
  Services --> Schemas

  OrgRoutes --> MockRunner
  MockRunner -->|"writes answers and logs"| Runs
  Services -->|"validates and scores"| Runs
```

## 3. Final Production Architecture

The final version keeps the same product loop but replaces local JSON and mock execution with durable cloud services, isolated runner workers, object storage, database state, and secure secret management.

```mermaid
flowchart TB
  subgraph Users["Users"]
    Team["Team users"]
    Organizer["Organizers"]
    Public["Public viewers"]
  end

  subgraph WebApp["Web App"]
    Frontend["Frontend<br/>Tournament UI"]
    API["Backend API<br/>Auth, routes, validation, orchestration"]
  end

  subgraph Persistence["Persistence"]
    DB["Oracle Database<br/>Canonical relational state<br/>JSON run payloads"]
    ObjectStorage["OCI Object Storage<br/>ZIP uploads, snapshots, artifacts, run files"]
    VectorMemory["Vector Store / Oracle Vector Search<br/>Team-private memory and shared rules memory"]
  end

  subgraph Operations["Execution And Operations"]
    Scheduler["Scheduler / Manual Trigger<br/>Nightly runs and organizer overrides"]
    Queue["Run Queue<br/>One task per team per matchday"]
    Worker["Runner Worker<br/>Build prompt, attach artifacts, start sandbox"]
    Container["Hosted Container Sandbox<br/>Network restricted, short-lived, one team run"]
    Logs["Logging And Monitoring<br/>Run traces, errors, scoring audit"]
  end

  subgraph External["External Services"]
    FootballAPI["Football Data Provider<br/>API-Sports or official source"]
    HostedModel["Hosted AI Model<br/>Agent reasoning with Shell Tool"]
    Vault["OCI Vault<br/>API keys, signing secrets, provider credentials"]
  end

  Team --> Frontend
  Organizer --> Frontend
  Public --> Frontend
  Frontend --> API

  API --> DB
  API --> ObjectStorage
  API --> VectorMemory
  API --> Vault
  API --> Logs

  Organizer -->|"approve matchday data<br/>trigger run<br/>publish results"| API
  Scheduler --> Queue
  API --> Queue
  Queue --> Worker

  Worker --> DB
  Worker --> ObjectStorage
  Worker --> VectorMemory
  Worker --> Vault
  Worker --> Container
  Container --> HostedModel
  HostedModel -->|"answers.json<br/>strategy_summary.txt"| Container
  Container --> Worker
  Worker -->|"raw response, answers, validation, scoring"| ObjectStorage
  Worker -->|"canonical run record and leaderboard totals"| DB
  Worker --> Logs

  API --> FootballAPI
  FootballAPI -->|"raw provider responses"| ObjectStorage
  API -->|"normalized official matchday files"| ObjectStorage
```

## 4. Core Matchday Run Sequence

This is the most important lifecycle. A matchday starts as draft data, becomes official artifacts, runs all accepted team Skills, then becomes published results.

```mermaid
sequenceDiagram
  autonumber
  actor Organizer
  participant UI as Frontend UI
  participant API as Backend API
  participant DB as State Store / Oracle DB
  participant Files as Object Storage / Local data/
  participant Builder as Artifact Builder
  participant Queue as Run Queue
  participant Worker as Runner Worker
  participant Sandbox as Agent Sandbox
  participant Validator as Answer Validator
  participant Scorer as Scoring Engine
  participant Public as Public Views

  Organizer->>UI: Create or select matchday
  UI->>API: POST /api/org/matchdays
  API->>DB: Save matchday draft

  Organizer->>UI: Import or approve official data
  UI->>API: Import football/provider data
  API->>Files: Cache raw provider responses
  API->>DB: Save normalized teams, players, matches, claims

  Organizer->>UI: Build artifacts
  UI->>API: POST /api/org/matchdays/{id}/build-artifacts
  API->>Builder: Build tournament bundle
  Builder->>Files: Write tournament/rules.md
  Builder->>Files: Write answer schemas
  Builder->>Files: Write matchday.json, players.json, matches.json, risk-claims.json, standings.json
  Builder->>DB: Mark artifacts built

  Organizer->>UI: Trigger agent runs
  UI->>API: POST /api/org/matchdays/{id}/run
  API->>DB: Read accepted team snapshots
  API->>Queue: Enqueue one run per team

  loop Each team
    Queue->>Worker: RunTeamMatchday(team_id, matchday_id)
    Worker->>DB: Load team, snapshot, prior runs, standings
    Worker->>Files: Download skill snapshot and tournament artifacts
    Worker->>Sandbox: Create isolated sandbox
    Worker->>Sandbox: Attach Skills and official artifacts
    Worker->>Sandbox: Prompt agent to write answers.json and strategy_summary.txt
    Sandbox-->>Worker: Return generated files and raw response
    Worker->>Validator: Validate fantasy_xi, risk_play, strategy_summary
    Validator-->>Worker: Section-level validation result
    Worker->>Scorer: Score valid Fantasy XI and Risk Play
    Scorer-->>Worker: Fantasy points, risk points, bracket points
    Worker->>Files: Store prompt, answers, raw response, validation, scoring, logs
    Worker->>DB: Save run record and scoring totals
  end

  API->>DB: Rebuild leaderboard
  Organizer->>UI: Review run errors and scoring details
  Organizer->>UI: Publish matchday
  UI->>API: POST /api/org/matchdays/{id}/publish
  API->>DB: Mark matchday published
  Public->>API: GET leaderboard and matchday results
  API-->>Public: Published standings and result summaries
```

## 5. Team Submission Lifecycle

Teams can submit either a ZIP package or a GitHub repo URL. The local POC validates ZIP shape and stores repo URLs as accepted placeholders. The production app should clone/fetch repository snapshots after cutoff and validate them before execution.

```mermaid
stateDiagram-v2
  [*] --> Registered: Team creates account
  Registered --> SubmittedZip: Upload ZIP package
  Registered --> SubmittedRepo: Submit GitHub URL

  SubmittedZip --> Rejected: Invalid ZIP, unsafe paths, missing skills/SKILL.md
  SubmittedZip --> AcceptedSnapshot: Valid package shape

  SubmittedRepo --> PendingFetch: Repo URL recorded
  PendingFetch --> Rejected: Clone/fetch fails or package invalid
  PendingFetch --> AcceptedSnapshot: Repo fetched and package valid

  Rejected --> SubmittedZip: Upload fixed ZIP
  Rejected --> SubmittedRepo: Submit fixed repo URL

  AcceptedSnapshot --> LockedForMatchday: Cutoff passes
  LockedForMatchday --> RunQueued: Organizer or scheduler triggers run
  RunQueued --> Running: Worker starts isolated run
  Running --> FailedRun: Runner timeout or unrecoverable error
  Running --> Validated: Answers produced
  Validated --> Scored: Valid sections scored
  FailedRun --> RunHistory: Logs preserved
  Scored --> RunHistory: Results saved
  RunHistory --> AcceptedSnapshot: Team improves Skill for future matchday
```

## 6. Artifact Bundle Contents

Artifacts are the official input for each agent run. The sandbox should treat these files as authoritative.

```mermaid
flowchart TB
  Matchday["Matchday ID<br/>MD-001"]
  Bundle["tournament/"]
  Rules["rules.md<br/>Plain-English scoring and answer instructions"]
  Formats["answer-formats/"]
  Data["data/"]

  Matchday --> Bundle
  Bundle --> Rules
  Bundle --> Formats
  Bundle --> Data

  Formats --> FantasySchema["fantasy-xi.schema.json"]
  Formats --> RiskSchema["risk-play.schema.json"]
  Formats --> SummarySchema["strategy-summary.schema.json"]
  Formats --> BracketSchema["bracket.schema.json"]

  Data --> MatchdayJson["matchday.json<br/>matchday metadata and stage"]
  Data --> TeamsJson["teams.json<br/>public team catalog"]
  Data --> PlayersJson["players.json<br/>eligible player IDs, positions, teams"]
  Data --> MatchesJson["matches.json<br/>match IDs, teams, kickoff"]
  Data --> ClaimsJson["risk-claims.json<br/>claim IDs, categories, required fields"]
  Data --> StandingsJson["standings.json<br/>current leaderboard before run"]
```

## 7. Answer Validation And Fallback Policy

Validation should be section-level. A bad Risk Play should not destroy a valid Fantasy XI. A missing strategy summary should be a warning, not a scoring failure.

```mermaid
flowchart TB
  Answers["answers.json"]
  Fantasy["fantasy_xi"]
  Risk["risk_play"]
  Summary["strategy_summary"]

  Answers --> Fantasy
  Answers --> Risk
  Answers --> Summary

  Fantasy --> F1{"Exactly 11 IDs?"}
  F1 -->|No| FantasyInvalid["Fantasy invalid<br/>Reuse prior valid XI if legal<br/>Otherwise 0 fantasy points"]
  F1 -->|Yes| F2{"All IDs eligible?"}
  F2 -->|No| FantasyInvalid
  F2 -->|Yes| F3{"Position counts valid?"}
  F3 -->|No| FantasyInvalid
  F3 -->|Yes| FantasyValid["Fantasy valid<br/>Score player events"]

  Risk --> R1{"Null?"}
  R1 -->|Yes| RiskSkipped["Risk skipped<br/>0 risk points"]
  R1 -->|No| R2{"Claim ID exists?"}
  R2 -->|No| RiskInvalid["Risk invalid<br/>Treat as skipped"]
  R2 -->|Yes| R3{"Required fields match claim?"}
  R3 -->|No| RiskInvalid
  R3 -->|Yes| RiskValid["Risk valid<br/>Apply stake"]

  Summary --> S1{"Plain text and non-empty?"}
  S1 -->|No| SummaryWarning["Warning<br/>Do not block scoring"]
  S1 -->|Yes| SummaryValid["Store summary"]

  FantasyValid --> RunRecord["Run record"]
  FantasyInvalid --> RunRecord
  RiskValid --> RunRecord
  RiskSkipped --> RunRecord
  RiskInvalid --> RunRecord
  SummaryValid --> RunRecord
  SummaryWarning --> RunRecord
```

## 8. Fantasy XI Scoring Flow

The scoring engine reads the selected players and applies real match events from the official source.

```mermaid
flowchart LR
  XI["Valid fantasy_xi<br/>11 player IDs"]
  Events["Official player events<br/>starts, minutes, goals, assists, cards, saves, clean sheet"]
  Position["Player position<br/>GK, DEF, MID, FWD"]
  PlayerScore["Player point breakdown"]
  FantasyTotal["Fantasy XI total"]

  XI --> Events
  XI --> Position
  Events --> PlayerScore
  Position --> PlayerScore
  PlayerScore --> FantasyTotal

  subgraph Rules["Draft scoring rules"]
    Starts["+2 start"]
    Minutes["+2 played 60+ minutes"]
    Goal["+6 goal"]
    Assist["+4 assist"]
    CleanSheet["+4 clean sheet for GK/DEF"]
    Saves["+2 GK 3+ saves"]
    Yellow["-1 yellow card"]
    Red["-3 red card"]
    OwnGoal["-3 own goal"]
  end

  Rules --> PlayerScore
```

## 9. Risk Play Scoring Flow

Risk Play is optional. Stake depends on the team's score before the matchday.

```mermaid
flowchart TB
  PriorScore["Team points before matchday"]
  Claim["Selected Risk Play claim"]
  Category{"Claim category"}
  Stake["Stake points"]
  Outcome{"Claim outcome"}
  Add["Add stake"]
  Subtract["Subtract stake"]
  Total["Run risk_points"]

  PriorScore --> Stake
  Claim --> Category
  Category -->|"Green"| Green["15 percent stake"]
  Category -->|"Yellow"| Yellow["25 percent stake"]
  Category -->|"Red"| Red["35 percent stake"]
  Green --> Stake
  Yellow --> Stake
  Red --> Stake
  Claim --> Outcome
  Outcome -->|"Correct"| Add
  Outcome -->|"Incorrect"| Subtract
  Add --> Total
  Subtract --> Total
```

## 10. Main Data Model

Phase 1 stores these as JSON files. Production should store the canonical records in Oracle Database and store large generated artifacts in Object Storage.

```mermaid
erDiagram
  TEAM ||--o{ SUBMISSION : creates
  TEAM ||--o{ SKILL_SNAPSHOT : owns
  TEAM ||--o{ RUN : receives
  MATCHDAY ||--o{ RUN : contains
  MATCHDAY ||--o{ ARTIFACT_BUNDLE : builds
  SUBMISSION ||--o{ SKILL_SNAPSHOT : produces
  SKILL_SNAPSHOT ||--o{ RUN : used_by
  RUN ||--o{ RISK_CLAIM_RESULT : includes
  RUN ||--o{ RUN_FILE : stores
  TEAM ||--o{ TEAM_MEMORY_ITEM : owns

  TEAM {
    string id PK
    string name
    json members
    string token_hash
    string submission_method
    string repo_url
    timestamp created_at
  }

  SUBMISSION {
    string id PK
    string team_id FK
    string source
    string path_or_repo_url
    boolean accepted
    json errors
    json warnings
    timestamp created_at
  }

  SKILL_SNAPSHOT {
    string id PK
    string team_id FK
    string submission_id FK
    string matchday_id
    string source
    string storage_path
    boolean accepted
    json validation
    timestamp created_at
  }

  MATCHDAY {
    string id PK
    string label
    string stage
    string status
    date match_date
    string artifact_uri
    json normalized_data
    timestamp published_at
  }

  RUN {
    string id PK
    string team_id FK
    string matchday_id FK
    string snapshot_id FK
    string status
    string runner
    json answers
    json validation
    json scoring
    decimal fantasy_points
    decimal risk_points
    decimal bracket_points
    decimal total_points
    text strategy_summary
    timestamp created_at
  }

  RISK_CLAIM_RESULT {
    string id PK
    string run_id FK
    string claim_id
    string category
    decimal stake_points
    string outcome
    decimal points_earned
  }

  RUN_FILE {
    string id PK
    string run_id FK
    string file_type
    string object_uri
  }

  TEAM_MEMORY_ITEM {
    string id PK
    string team_id FK
    string visibility
    string source_type
    text content_text
    json metadata
    string vector_ref
  }
```

## 11. UI Screens And Data Sources

```mermaid
flowchart TB
  subgraph UI["Frontend Screens"]
    Home["Home<br/>current standings, next matchday, latest results"]
    Leaderboard["Leaderboard<br/>rank, team, total, fantasy, risk, bracket"]
    Results["Matchday Results<br/>answers, player points, risk outcome, summaries"]
    Catalog["Data Catalog<br/>schemas and visible fields"]
    TeamDash["Team Dashboard<br/>submissions, snapshots, run history"]
    Upload["Team Upload<br/>ZIP or repo URL"]
    Org["Organizer Console<br/>data import, artifact build, run, publish"]
  end

  subgraph API["API Routes"]
    PublicAPI["Public API<br/>leaderboard, matchdays, results, catalog"]
    TeamAPI["Team API<br/>register, login, upload, repo, runs"]
    OrgAPI["Organizer API<br/>matchdays, artifacts, run, score, publish, logs"]
  end

  Home --> PublicAPI
  Leaderboard --> PublicAPI
  Results --> PublicAPI
  Catalog --> PublicAPI
  TeamDash --> TeamAPI
  Upload --> TeamAPI
  Org --> OrgAPI
```

## 12. Privacy And Exposure Boundaries

The system must keep public data, team-private data, and hidden run data separate.

```mermaid
flowchart TB
  PublicData["Public data<br/>published leaderboard, matchday summaries, data catalog"]
  TeamPrivate["Team-private data<br/>team token, submissions, snapshots, run logs, raw agent output"]
  HiddenData["Hidden official data<br/>unpublished provider values, future matchday scoring inputs"]

  PublicUI["Public UI"]
  TeamUI["Team Dashboard"]
  OrgUI["Organizer Console"]
  Sandbox["Single-team sandbox"]

  PublicData --> PublicUI
  PublicData --> TeamUI
  PublicData --> OrgUI

  TeamPrivate --> TeamUI
  TeamPrivate --> OrgUI
  TeamPrivate --> Sandbox

  HiddenData --> OrgUI
  HiddenData --> Sandbox

  HiddenData -. "never before allowed time" .-> PublicUI
  TeamPrivate -. "never to other teams" .-> PublicUI
  TeamPrivate -. "never to another team's sandbox" .-> Sandbox
```

## 13. Recommended Implementation Stages

```mermaid
flowchart LR
  S1["1. Local POC<br/>FastAPI, static UI, JSON state, mock runner"]
  S2["2. Better local loop<br/>ZIP validation, artifacts, answer validation, scoring, risk"]
  S3["3. Football data adapter<br/>API-Sports cache, normalization, organizer review"]
  S4["4. Hosted runner<br/>container sandbox, Skill ZIP, Shell Tool, file retrieval"]
  S5["5. Durable storage<br/>Oracle Database and Object Storage"]
  S6["6. Team memory<br/>private vector retrieval and shared rules memory"]
  S7["7. Production operations<br/>scheduler, queue, observability, audit, deployment"]

  S1 --> S2 --> S3 --> S4 --> S5 --> S6 --> S7
```

## 14. End-State Summary

At the end, the system should behave like this:

1. Teams register and submit Skills.
2. The app validates and snapshots accepted Skills.
3. Organizers approve official matchday data.
4. The app builds official tournament artifacts.
5. A scheduler or organizer trigger creates one isolated run per team.
6. Each sandbox receives only the team Skill snapshot and official artifacts for that run.
7. The agent writes structured answers.
8. The app validates each answer section independently.
9. The scoring engine applies official match events, Risk Play outcomes, and bracket points.
10. The app persists the full audit trail privately.
11. Organizers review edge cases.
12. Published results update the public leaderboard and matchday pages.
13. Team-private run history and lessons can feed future team memory without leaking to other teams.
