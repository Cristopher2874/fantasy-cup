import { ExecutionDetails } from './ExecutionDetails';
import { ResultMessages } from '../ResultMessages';
import { PipelineJob, ValidationResult } from '../../types';
import { statusClass } from '../../utils/formatters';

type ValidationJobCardProps = {
  result: ValidationResult;
  job?: PipelineJob;
  streamAlert?: string;
};

type RecentJobCardProps = {
  job: PipelineJob;
  streamAlert?: string;
};

export function ValidationJobCard({ result, job, streamAlert }: ValidationJobCardProps) {
  return (
    <article className="result-card">
      <div className="result-title">
        <div>
          <span className="filename">{result.filename}</span>
          <h3>{result.skill_name ?? 'Skill package'}</h3>
        </div>
        <span className={`status-pill ${result.valid ? 'status-valid' : 'status-invalid'}`}>{result.status}</span>
      </div>

      <ResultMessages title="Issues" messages={result.issues ?? []} tone="error" />
      <ResultMessages title="Warnings" messages={result.warnings ?? []} tone="warning" />

      {result.execution_job_id ? (
        <ExecutionDetails job={job} jobId={result.execution_job_id} streamAlert={streamAlert} />
      ) : (
        <p className="muted-text">This package did not enter execution.</p>
      )}
    </article>
  );
}

export function RecentJobCard({ job, streamAlert }: RecentJobCardProps) {
  return (
    <article className="result-card">
      <div className="result-title">
        <div>
          <span className="filename">{job.filename ?? job.job_id}</span>
          <h3>{job.skill_name ?? 'Execution job'}</h3>
        </div>
        <span className={`status-pill ${statusClass(job.status)}`}>{job.status}</span>
      </div>
      <ExecutionDetails job={job} jobId={job.job_id} streamAlert={streamAlert} />
    </article>
  );
}
