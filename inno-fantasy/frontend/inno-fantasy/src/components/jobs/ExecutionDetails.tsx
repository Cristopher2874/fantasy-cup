import { ResultMessages } from '../ResultMessages';
import { PipelineJob } from '../../types';
import { formatTimestamp, statusClass } from '../../utils/formatters';

type ExecutionDetailsProps = {
  job?: PipelineJob;
  jobId: string;
  streamAlert?: string;
};

export function ExecutionDetails({ job, jobId, streamAlert }: ExecutionDetailsProps) {
  if (!job) {
    return (
      <div className="execution-box">
        <span className="status-pill status-neutral">queued</span>
        <p>Waiting for the first execution update.</p>
        <code>{jobId}</code>
      </div>
    );
  }

  return (
    <div className="execution-box">
      <div className="execution-line">
        <span className={`status-pill ${statusClass(job.status)}`}>{job.status}</span>
        <span>{job.stage ?? 'queued'}</span>
      </div>
      <p>{job.message ?? 'Execution update received.'}</p>
      <dl className="job-meta">
        <div>
          <dt>Job ID</dt>
          <dd>{job.job_id}</dd>
        </div>
        {job.updated_at && (
          <div>
            <dt>Updated</dt>
            <dd>{formatTimestamp(job.updated_at)}</dd>
          </div>
        )}
        {typeof job.runner?.return_code !== 'undefined' && (
          <div>
            <dt>Return code</dt>
            <dd>{job.runner.return_code ?? 'n/a'}</dd>
          </div>
        )}
      </dl>

      {job.runner?.submission_path && (
        <div className="success-note">Submission JSON produced and ready for the scoring phase.</div>
      )}

      <ResultMessages title="Execution issues" messages={job.issues ?? []} tone="error" />
      <ResultMessages title="Execution warnings" messages={job.warnings ?? []} tone="warning" />
      <ResultMessages title="Runner notes" messages={job.runner?.notes ?? []} tone="warning" />

      {streamAlert && <div className="alert alert-warning">{streamAlert}</div>}
    </div>
  );
}
