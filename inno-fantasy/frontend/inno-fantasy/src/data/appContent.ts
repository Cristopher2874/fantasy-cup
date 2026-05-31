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

export const packageRules = [
  'Upload ZIP files only.',
  'Submit up to five skills in one batch.',
  'Each ZIP must be 5 MB or smaller.',
  'Each skill needs exactly one SKILL.md file.',
  'Allowed top-level entries are SKILL.md, agents, references, and assets.',
  'Scripts, executable files, secrets, private keys, and tokens are rejected.',
];
