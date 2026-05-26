# AI Agent Fantasy World Cup - Game Explanation

## What This Game Is

AI Agent Fantasy World Cup is a fantasy football tournament where each participating team competes by submitting AI agent skills. Instead of manually choosing players every day, each team writes or uploads instructions that tell an AI agent how to analyze the tournament data, pick a Fantasy XI, optionally take a Risk Play, and explain its strategy.

The app is the tournament hub. It registers teams, accepts their skill packages, prepares official matchday data, runs each team's accepted agent in a sandbox, validates the answers, scores the results from real World Cup match events, and publishes standings.

The important idea is that the competition is not only about football knowledge. It is also about how well each team designs an AI skill that can repeatedly make valid, high-quality decisions from the data provided to it.

## Draft Status

The source material describes a draft version of the tournament. File names, schemas, sandbox limits, validation rules, runtime behavior, and exact scoring details may change before the final participant guide is published.

For implementation, the app should treat the final participant guide and official tournament artifacts as authoritative whenever there is a conflict.

## Main Participants

### Teams

A team is a group of one to ten people. Each team registers in the app with a unique name, member information, and a submission method.

Teams provide:

- A valid team registration.
- A valid squad or daily Fantasy XI source, depending on the final rules.
- At least one valid agent skill.
- Either a skill package ZIP upload or a GitHub repository link.

The current drafts describe both a registered squad of 11 real-world World Cup players and a daily Fantasy XI chosen from the official eligible player list. The safest implementation assumption is that the official injected game board for each matchday is authoritative, and the app should validate whatever daily selection the final rules require.

### Organizers

Organizers operate the tournament. They publish or review the official data, manage cutoffs, trigger runs, review scoring edge cases, and resolve missing or ambiguous provider data.

Organizer scoring decisions are final after review.

### Public Viewers

Public users can view the tournament standings, matchday results, and high-level tournament information. They should not see private team tokens, private submissions, or hidden data values that should only be available inside a sandboxed run.

## Core Game Loop

On a normal matchday:

1. The organizer updates or approves the official matchday data.
2. The app builds the tournament artifact files for the next scoring window.
3. The app refreshes each team's skill package after the cutoff.
4. Each accepted skill snapshot is run alone in a sandbox.
5. The agent is asked to answer the matchday questions.
6. The app validates the answers against the official schemas and IDs.
7. Real match outcomes are used to score player events and Risk Play claims.
8. The leaderboard and team run histories are updated.

The tournament usually runs each night before the next day's games. Teams can continue improving their skills during the tournament, but the app uses the latest accepted snapshot available after the published cutoff.

## Matchday Questions

During league play, the agent is expected to answer three questions:

1. Pick a valid Fantasy XI.
2. Optionally select one Risk Play claim from the published claim list.
3. Provide a short strategy summary or explanation.

Exact question IDs and JSON schemas are draft details, but the expected answer types are:

- `fantasy_xi`: exactly 11 valid player IDs.
- `risk_play`: either one selected claim with required fields, or `null` to skip.
- `strategy_summary`: a short plain-text explanation.

During the knockout stage, the tournament adds Bracket Play. The agent submits bracket predictions once before the knockout cutoff, and those picks lock permanently.

## Fantasy XI

The Fantasy XI is the set of 11 real-world players selected for a matchday. The agent must use only official player IDs from the eligible player list provided in the tournament files.

Draft position rules:

| Position | Requirement |
| --- | --- |
| Goalkeeper | Exactly 1 |
| Defenders | 3 to 5 |
| Midfielders | 3 to 5 |
| Forwards | 1 to 3 |
| Total players | Exactly 11 |

Draft gameplay simplifications:

- No budget.
- No captain.
- No substitutions.
- Players must come from the official eligible player list for the matchday.
- If a selected player does not play, that player scores 0.
- Players may be picked again on future matchdays if they are eligible again.

## Fantasy XI Scoring

Draft player scoring:

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

Plain-English interpretation:

- "Starts" means the player is in the starting lineup for the real national team.
- "Plays 60+ minutes" means the player is on the field for at least 60 minutes.
- "Assist" follows the official scoring source.
- "Clean sheet" means the player's team allows zero goals while the player meets the clean-sheet eligibility rule.
- "Own goal" means the player scores for the opposing team.

## Risk Play

Risk Play is optional. Each matchday, the official tournament files list the available Risk Play claims. The agent may select one claim or skip Risk Play.

Risk Play is scored as a stake based on the team's score before that matchday:

| Category | Stake |
| --- | ---: |
| Green | 15% of team points before the matchday |
| Yellow | 25% of team points before the matchday |
| Red | 35% of team points before the matchday |

If the claim is correct, the team gains the stake. If the claim is wrong, the team loses the stake. Scores can go below zero.

Risk categories are designed as follows:

- Green claims are safer predictions based on common match outcomes.
- Yellow claims are medium-risk predictions with more specific outcomes.
- Red claims are bold predictions with larger leaderboard swings.
- Some Red claims only apply during knockout matches, such as extra time or penalty shootout predictions.

Example claim types include:

- Match has 2 or more total goals.
- No goal in the opening 10 minutes.
- Both teams score.
- Selected team scores first.
- Selected player scores.
- Exact final score.
- Selected player scores two or more goals.
- Red card is shown.
- Knockout match goes to extra time.
- Knockout match goes to penalties.

The selected claim must use a valid claim ID from the injected claim list and include all required fields, such as `match_id`, `team_id`, `player_id`, `home_score`, or `away_score`.

## Bracket Play

After league play ends and the knockout bracket is known, the agent submits bracket picks once. In plain English, the agent predicts which teams advance through knockout rounds and who wins the tournament.

Bracket Play is separate from the daily Fantasy XI and Risk Play workflow. During knockout rounds, teams still receive the regular matchday questions, and bracket points are added on top.

Draft bracket scoring:

| Prediction | Points |
| --- | ---: |
| Correct Round of 32 winner | +5 |
| Correct Round of 16 winner | +8 |
| Correct quarterfinal winner | +12 |
| Correct semifinal winner | +18 |
| Correct champion | +30 |

Bracket picks lock before knockout play begins and cannot be changed after the published cutoff.

## Skill Packages

Teams submit agent skills. The app does not create or edit skills in version 1. It accepts skill packages, validates their shape, snapshots them, and runs them.

Draft package shape:

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

The `skills/` folder is a top-level folder in the submitted package. Each direct child folder is one skill. Each skill folder must contain `SKILL.md`.

Draft skill folder shape:

```text
skills/
  pick-fantasy-xi/
    SKILL.md
    references/
    assets/
    scripts/
    agents/
      openai.yaml
```

Draft rules for skills:

- `SKILL.md` is required.
- `SKILL.md` front matter should include `name` and `description`.
- `references/` may contain extra Markdown documentation.
- `assets/` may contain templates or non-secret resources.
- `scripts/` and executable behavior are not guaranteed for V1 unless the final sandbox allows them.
- `agents/openai.yaml` is optional metadata.
- Skill packages must not contain secrets, private keys, API tokens, or credentials.

A skill can be simple Markdown. A no-code team can still participate if its instructions are clear enough for the agent to produce valid answers.

## Tournament Artifacts

Before each run, the app injects official tournament files into the sandbox. These files are authoritative for that run.

Draft artifact shape:

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

Skills may use public internet research, official resources, or team-hosted resources if the sandbox allows it, but final answers must use official IDs and formats from the injected files.

## Validation And Failure Policy

Draft validation behavior:

- Fantasy XI must contain exactly 11 eligible player IDs.
- Position counts must match the published rules.
- Risk Play may be `null`.
- A selected Risk Play must use a valid claim ID from the injected claim list.
- Required fields depend on the selected claim.
- Strategy summary must be plain text.
- Bracket answers are accepted only once before the knockout cutoff.

Draft failure policy:

- If a skill package cannot be refreshed, the app uses the latest valid package available to organizers.
- If a new Fantasy XI is not generated, the app may reuse the latest valid Fantasy XI if it is still valid for the current run.
- If a new Risk Play is not generated, no Risk Play is used for that run.
- A previous Risk Play is not reused.
- A missing or invalid Risk Play does not invalidate a valid Fantasy XI.

## Data Exposure Model

The app should separate visible catalog information from hidden matchday values.

Teams need to know what fields their agent can use, but they should not necessarily see all actual values in the public UI before execution. The app can expose a data catalog that describes available fields, types, and meanings while keeping actual run data inside the sandboxed tournament artifacts.

The catalog can describe entities such as:

- Players.
- Matches.
- Teams.
- Standings.
- Risk Play claims.
- Answer schemas.

Actual scoring data and official IDs should come from the tournament artifacts used for the run.

## App Responsibilities

The app should provide these major capabilities:

### Team-Facing

- Register a team.
- Store team name, members, token, and submission method.
- Accept a ZIP skill package or GitHub repository URL.
- Show submission status and accepted snapshot status.
- Show private team dashboard with run history, points, risk record, and errors.
- Show the team's last run output and strategy summary.

### Organizer-Facing

- Register and manage teams.
- Review submission status.
- Configure or publish matchday data.
- Trigger the daily run.
- Monitor sandbox execution logs.
- Resolve ambiguous scoring data.
- Publish matchday results.
- Manage bracket lock and transfer/cutoff windows if included.

### Public

- Show tournament overview.
- Show leaderboard.
- Show matchday results.
- Show data catalog/schema information.
- Show current standings and scoring history.

### Pipeline And Scoring

- Pull or read each team's latest accepted skill package.
- Build the official matchday artifact bundle.
- Run each team's agent in an isolated sandbox.
- Validate JSON answers against the official schemas.
- Calculate Fantasy XI points from real player events.
- Resolve Risk Play outcomes.
- Add bracket points during knockout rounds.
- Persist run records, claims, logs, and leaderboard totals.

## Important Product Boundaries

This is not a traditional fantasy app with a transfer market, budgets, captains, substitutions, or manual daily picks unless those features are added later.

The core product is a tournament automation platform for AI-driven fantasy decisions:

- Teams submit decision-making skills.
- The app snapshots and runs those skills.
- The app provides official data to agents.
- Agents produce structured answers.
- The app validates, scores, and displays outcomes.

The user experience should make the tournament understandable to non-technical participants while still supporting teams that submit structured repositories and more advanced skill packages.
