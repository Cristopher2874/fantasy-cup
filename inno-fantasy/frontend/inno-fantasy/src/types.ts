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
