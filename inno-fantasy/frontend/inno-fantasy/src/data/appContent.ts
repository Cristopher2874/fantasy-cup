import { NavigationItem } from '../types';

export const MAX_UPLOADS = 5;
export const MAX_ZIP_BYTES = 5 * 1024 * 1024;

export const navigation: NavigationItem[] = [
  { view: 'home', label: 'Home' },
  { view: 'about', label: 'About' },
  { view: 'submit', label: 'Submit' },
];

export const pitchMarkers = ['GK', 'DEF', 'DEF', 'MID', 'MID', 'MID', 'FWD', 'Risk', 'JSON'];

export const tournamentProcessSteps = [
  'Official matchday data is approved',
  'Skill package is refreshed after cutoff',
  'Accepted snapshot runs alone',
  'JSON answer is validated',
  'Scores update after real match events',
];

export const scoringRows = [
  ['Player starts', '+2'],
  ['Plays 60+ minutes', '+2'],
  ['Goal', '+6'],
  ['Assist', '+4'],
  ['Defender or goalkeeper clean sheet', '+4'],
  ['Goalkeeper makes 3+ saves', '+2'],
  ['Yellow card', '-1'],
  ['Red card or own goal', '-3'],
];

export const riskRows = [
  ['Green', '15%', 'Safer match outcome claims'],
  ['Yellow', '25%', 'Specific medium-risk claims'],
  ['Red', '35%', 'Bold claims with large swings'],
];

export const playerSelectionRules = [
  'Select exactly 11 players from the official eligible player list for the matchday.',
  'Use the `record_id` value from `players.json`; it represents one player in one match and usually looks like `match_id:player_id`.',
  'Each FantasyXI entry should be submitted as an object such as `{ "record_id": "12345:67890" }`.',
  'Position counts must be exactly 1 goalkeeper, 3 to 5 defenders, 3 to 5 midfielders, and 1 to 3 forwards.',
  'There is no budget, captain, bench, substitutions, or transfer market in this version.',
  'Players can be selected again on later matchdays only when they appear in that matchday eligible player list.',
  'If a selected real player does not play, that player contributes 0 points.',
];

export const answerFormatRules = [
  '`team_id`: team identifier from the upload form when provided.',
  '`team_name`: display name returned by the skill.',
  '`matchday_id`: matchday identifier from the provided public data.',
  '`answers.fantasy_xi`: exactly 11 entries with valid `record_id` values.',
  '`answers.risk_play`: one valid Risk Play object or `null` to skip.',
  '`answers.strategy_summary`: non-empty plain text explaining the strategy.',
];

export const riskClaimRows = [
  ['match_2plus_goals', 'Green', 'claim_id, match_id', 'Match finishes with at least 2 total goals.'],
  ['no_goal_first_10', 'Green', 'claim_id, match_id', 'No goal is scored from minute 1 through minute 10.'],
  ['goal_before_halftime', 'Green', 'claim_id, match_id', 'At least one goal is scored before halftime.'],
  ['match_2plus_cards', 'Green', 'claim_id, match_id', 'Match has at least 2 card events.'],
  ['both_teams_score', 'Yellow', 'claim_id, match_id', 'Both teams score at least once.'],
  ['match_over_2_5_goals', 'Yellow', 'claim_id, match_id', 'Match finishes with 3 or more total goals.'],
  ['team_scores_first', 'Yellow', 'claim_id, match_id, team_id', 'Selected team scores first.'],
  ['player_scores', 'Yellow', 'claim_id, match_id, player_id', 'Selected player scores at least one non-own goal.'],
  ['exact_score', 'Red', 'claim_id, match_id, home_score, away_score', 'Final score matches exactly.'],
  ['player_scores_2plus', 'Red', 'claim_id, match_id, player_id', 'Selected player scores at least 2 non-own goals.'],
  ['team_wins_by_3plus', 'Red', 'claim_id, match_id, team_id', 'Selected team wins by at least 3 goals.'],
  ['match_goes_to_extra_time', 'Red', 'claim_id, match_id', 'Knockout match reaches extra time.'],
  ['match_goes_to_penalties', 'Red', 'claim_id, match_id', 'Knockout match reaches a penalty shootout.'],
];

export const riskSelectionRules = [
  'Risk Play is optional; use `null` when skipping it.',
  'A team may submit at most one Risk Play claim per matchday.',
  'The claim must come from the available claims in `risk_claims.json` for that matchday.',
  'The submitted object must include all required fields for that claim type.',
  'If the claim is correct, the team gains the stake; if wrong, the team loses the stake.',
  'The stake is calculated from the team score before the matchday, and total scores can go below zero.',
];

export const packageRules = [
  'Upload only `.zip` files.',
  'Submit at most five ZIP files in one batch.',
  'Each ZIP must be 5 MB or smaller.',
  'The archive must be readable, non-empty, contain at most 100 files, and expand to 10 MB or less.',
  'ZIP member paths must be safe: no absolute paths, drive prefixes, null bytes, or `..` traversal.',
  'The ZIP must contain exactly one `SKILL.md`, either at the ZIP root or inside one top-level skill folder.',
  '`SKILL.md` must be named exactly `SKILL.md`, be UTF-8 text, and be 250 KB or smaller.',
  '`SKILL.md` must start with YAML front matter delimited by `---` and include only `name` and `description`.',
  '`name` must be lowercase letters, digits, and hyphens, under 64 characters, with no leading or trailing hyphen.',
  'If the ZIP uses a top-level skill folder, the folder name must match the front matter `name`.',
  '`description` must be non-empty and should clearly explain what the skill does.',
  'The body of `SKILL.md` must contain instructions. Very long bodies should move details into references.',
  'Allowed top-level entries are `SKILL.md`, `agents`, `references`, and `assets`.',
  '`agents`, `references`, and `assets` must be directories when present.',
  'Scripts and executable content are rejected, including `scripts`, `bin`, `cmd`, `.git`, `.github`, shell files, Python files, JavaScript files, binaries, executable permissions, and shebang scripts.',
  'Secrets, private keys, API tokens, credential exfiltration, hidden instructions, host-app prompt injection, network abuse, and filesystem sabotage are rejected.',
];
