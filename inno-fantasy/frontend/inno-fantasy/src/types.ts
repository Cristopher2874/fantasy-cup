import { FormEvent } from 'react';

export type View = 'home' | 'about' | 'submit';

export type NavigationItem = {
  view: View;
  label: string;
};

export type ValidationResult = {
  job_id: string;
  filename: string;
  valid: boolean;
  status: string;
  skill_name?: string | null;
  issues?: string[];
  warnings?: string[];
  ready_for_dispatch?: boolean;
  execution_job_id?: string;
  execution_status?: string;
};

export type UploadResponse = {
  job_id: string;
  team_id?: string | null;
  status: string;
  accepted: number;
  rejected: number;
  execution_status?: string;
  results: ValidationResult[];
};

export type RunnerResult = {
  success?: boolean;
  submission_path?: string | null;
  final_message_path?: string | null;
  stdout_path?: string | null;
  stderr_path?: string | null;
  prompt_path?: string | null;
  issues?: string[];
  notes?: string[];
  return_code?: number | null;
};

export type ScorePlayer = {
  record_id: string;
  match_id: string;
  player_id: string;
  name: string;
  team: string;
  position: 'GK' | 'DEF' | 'MID' | 'FWD' | string;
  points: number;
  breakdown?: string[];
};

export type FantasyScore = {
  valid: boolean;
  points: number;
  errors: string[];
  warnings: string[];
  players: ScorePlayer[];
  position_counts: Record<string, number>;
};

export type RiskScore = {
  valid: boolean;
  outcome: 'skipped' | 'invalid' | 'correct' | 'incorrect' | string;
  points: number;
  stake: number;
  errors: string[];
  warnings: string[];
  claim_id?: string | null;
  category?: 'green' | 'yellow' | 'red' | string;
  correct?: boolean;
  match_id?: string;
  evidence_path?: string;
};

export type TeamScoreResult = {
  team_id: string;
  team_name: string;
  previous_total_points: number;
  fantasy: FantasyScore;
  risk: RiskScore;
  strategy_summary?: string;
  fantasy_points: number;
  risk_points: number;
  total_delta: number;
  new_total_points: number;
  status: 'scored' | 'scored_with_errors' | string;
  matchday_id?: string | null;
};

export type ScoreResult = {
  schema_version: string;
  generated_at: string;
  job_id: string;
  matchday_id?: string | null;
  truth_path?: string | null;
  submission_path?: string | null;
  leaderboard_path?: string | null;
  result: TeamScoreResult;
};

export type ScoreRunResult = {
  success: boolean;
  result_path?: string | null;
  leaderboard_path?: string | null;
  truth_path?: string | null;
  issues: string[];
  result?: ScoreResult | null;
};

export type LeaderboardTeam = {
  rank?: number;
  team_id: string;
  team_name: string;
  total_points: number;
  fantasy_points: number;
  risk_points: number;
  matchdays_played: number;
  last_status?: string;
  last_scored_at?: string;
};

export type Leaderboard = {
  schema_version: string;
  updated_at?: string | null;
  teams: LeaderboardTeam[];
};

export type ScoresResponse = {
  leaderboard: Leaderboard;
  scores: ScoreResult[];
};

export type PipelineJob = {
  job_id: string;
  validation_job_id?: string;
  team_id?: string | null;
  skill_name?: string | null;
  filename?: string | null;
  status: string;
  stage?: string;
  message?: string;
  created_at?: string;
  updated_at?: string;
  issues?: string[];
  warnings?: string[];
  runner?: RunnerResult | null;
  score_result_path?: string | null;
  score?: ScoreRunResult | null;
};

export type FileCheck = {
  file: File;
  ok: boolean;
  issue?: string;
};

export type TimelineState = 'idle' | 'active' | 'complete' | 'warning';

export type SubmitTab = 'upload' | 'jobs' | 'results';

export type SubmitController = {
  acceptedResults: ValidationResult[];
  executionResults: ValidationResult[];
  fileChecks: FileCheck[];
  hasClientIssues: boolean;
  isDragging: boolean;
  isSubmitting: boolean;
  progressJobs: Record<string, PipelineJob>;
  recentJobs: PipelineJob[];
  rejectedResults: ValidationResult[];
  selectedFiles: File[];
  streamAlerts: Record<string, string>;
  submitError: string | null;
  teamId: string;
  uploadResponse: UploadResponse | null;
  handleFiles: (files: FileList | File[]) => void;
  handleSubmit: (event: FormEvent<HTMLFormElement>) => void;
  refreshJobs: () => Promise<void>;
  removeFile: (index: number) => void;
  setIsDragging: (value: boolean) => void;
  setTeamId: (value: string) => void;
};
