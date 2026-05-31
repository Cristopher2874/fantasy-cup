import { PipelineJob, ScoreResult, TeamScoreResult } from '../types';

export function getScoreResult(job?: PipelineJob): ScoreResult | null {
  return job?.score?.result ?? null;
}

export function getTeamScore(job?: PipelineJob): TeamScoreResult | null {
  return getScoreResult(job)?.result ?? null;
}

export function hasScoreResult(job?: PipelineJob): boolean {
  return Boolean(getTeamScore(job));
}

export function formatPoints(value?: number | null, signed = false) {
  if (typeof value !== 'number' || Number.isNaN(value)) {
    return signed ? '+0' : '0';
  }

  return new Intl.NumberFormat(undefined, {
    maximumFractionDigits: 2,
    minimumFractionDigits: Number.isInteger(value) ? 0 : 2,
    signDisplay: signed ? 'always' : 'auto',
  }).format(value);
}

export function scoreTone(status?: string, valid = true) {
  if (!valid || status === 'scored_with_errors' || status === 'invalid') {
    return 'status-invalid';
  }
  if (status === 'scored' || status === 'correct' || status === 'skipped') {
    return 'status-valid';
  }
  return 'status-neutral';
}
