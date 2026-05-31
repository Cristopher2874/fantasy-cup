import { PipelineJob, TimelineState, ValidationResult } from '../types';
import { hasScoreResult } from './scoreUtils';

export function executionState(
  results: ValidationResult[],
  progressJobs: Record<string, PipelineJob>,
): TimelineState {
  const jobs = getExecutionJobs(results, progressJobs);

  if (jobs.length === 0) {
    return 'active';
  }
  if (jobs.some((job) => job.status === 'failed')) {
    return 'warning';
  }
  if (jobs.every((job) => job.status === 'completed')) {
    return 'complete';
  }
  return 'active';
}

export function scoreState(results: ValidationResult[], progressJobs: Record<string, PipelineJob>): TimelineState {
  const jobs = getExecutionJobs(results, progressJobs);
  if (jobs.length === 0) {
    return 'idle';
  }
  if (jobs.some((job) => job.stage === 'scoring_failed' || job.score?.success === false)) {
    return 'warning';
  }
  if (jobs.every((job) => hasScoreResult(job) || job.stage === 'scored')) {
    return 'complete';
  }
  if (jobs.some((job) => job.stage === 'scoring' || job.status === 'completed')) {
    return 'active';
  }
  return 'idle';
}

function getExecutionJobs(results: ValidationResult[], progressJobs: Record<string, PipelineJob>) {
  return results
    .map((result) => (result.execution_job_id ? progressJobs[result.execution_job_id] : undefined))
    .filter(Boolean) as PipelineJob[];
}
