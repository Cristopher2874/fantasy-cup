import { RecentJobCard, ValidationJobCard } from '../jobs/JobCard';
import { ScoreboardPanel } from '../scores/ScoreboardPanel';
import { PipelineJob, UploadResponse } from '../../types';

type ResultsSectionProps = {
  progressJobs: Record<string, PipelineJob>;
  recentJobs: PipelineJob[];
  streamAlerts: Record<string, string>;
  uploadResponse: UploadResponse | null;
};

export function ResultsSection({ progressJobs, recentJobs, streamAlerts, uploadResponse }: ResultsSectionProps) {
  if (!uploadResponse && recentJobs.length === 0) {
    return (
      <div className="result-band">
        <ScoreboardPanel />
        <section className="empty-section">
          <span className="section-kicker">Server feedback</span>
          <h2>No results yet</h2>
          <p>Submit a ZIP batch or refresh execution jobs to inspect backend feedback.</p>
        </section>
      </div>
    );
  }

  return (
    <section className="result-band">
      <ScoreboardPanel />

      <div className="result-header">
        <div>
          <span className="section-kicker">Server feedback</span>
          <h2>Validation and execution results</h2>
        </div>
      </div>

      {uploadResponse && (
        <div className="results-grid">
          {uploadResponse.results.map((result) => {
            const jobId = result.execution_job_id;
            return (
              <ValidationJobCard
                key={result.job_id}
                result={result}
                job={jobId ? progressJobs[jobId] : undefined}
                streamAlert={jobId ? streamAlerts[jobId] : undefined}
              />
            );
          })}
        </div>
      )}

      {!uploadResponse && recentJobs.length > 0 && (
        <div className="results-grid">
          {recentJobs.slice(0, 6).map((job) => (
            <RecentJobCard key={job.job_id} job={job} streamAlert={streamAlerts[job.job_id]} />
          ))}
        </div>
      )}
    </section>
  );
}
