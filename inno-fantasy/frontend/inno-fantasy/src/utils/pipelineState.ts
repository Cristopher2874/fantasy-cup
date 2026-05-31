import { PipelineJob, TimelineState, ValidationResult } from '../types';

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
  return jobs.length > 0 && jobs.every((job) => job.status === 'completed') ? 'active' : 'idle';
}

function getExecutionJobs(results: ValidationResult[], progressJobs: Record<string, PipelineJob>) {
  return results
    .map((result) => (result.execution_job_id ? progressJobs[result.execution_job_id] : undefined))
    .filter(Boolean) as PipelineJob[];
}
