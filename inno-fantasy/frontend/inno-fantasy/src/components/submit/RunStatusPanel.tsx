import { TimelineStep } from '../TimelineStep';
import { PipelineJob, UploadResponse, ValidationResult } from '../../types';
import { executionState, scoreState } from '../../utils/pipelineState';
import { formatPoints, getTeamScore } from '../../utils/scoreUtils';

type RunStatusPanelProps = {
  acceptedResults: ValidationResult[];
  executionResults: ValidationResult[];
  isSubmitting: boolean;
  progressJobs: Record<string, PipelineJob>;
  rejectedResults: ValidationResult[];
  uploadResponse: UploadResponse | null;
};

export function RunStatusPanel({
  acceptedResults,
  executionResults,
  isSubmitting,
  progressJobs,
  rejectedResults,
  uploadResponse,
}: RunStatusPanelProps) {
  const executionJobs = executionResults
    .map((result) => (result.execution_job_id ? progressJobs[result.execution_job_id] : undefined))
    .filter(Boolean) as PipelineJob[];
  const scoredTeams = executionJobs.map(getTeamScore).filter(Boolean);
  const latestScore = scoredTeams[0];

  return (
    <aside className="run-panel" aria-label="Submission status">
      <div className="panel-heading">
        <h2>Run status</h2>
        <span className="status-pill status-neutral">{uploadResponse ? uploadResponse.status : 'Idle'}</span>
      </div>

      <div className="timeline">
        <TimelineStep label="Upload" state={uploadResponse ? 'complete' : isSubmitting ? 'active' : 'idle'} />
        <TimelineStep
          label="Validate"
          state={uploadResponse ? (uploadResponse.rejected > 0 ? 'warning' : 'complete') : 'idle'}
        />
        <TimelineStep
          label="Execute"
          state={executionResults.length > 0 ? executionState(executionResults, progressJobs) : 'idle'}
        />
        <TimelineStep label="Score" state={scoreState(executionResults, progressJobs)} />
      </div>

      {uploadResponse ? (
        <div className="batch-summary">
          <div>
            <span>Accepted</span>
            <strong>{acceptedResults.length}</strong>
          </div>
          <div>
            <span>Rejected</span>
            <strong>{rejectedResults.length}</strong>
          </div>
          <div>
            <span>Execution jobs</span>
            <strong>{executionResults.length}</strong>
          </div>
        </div>
      ) : (
        <p className="muted-text">Submission results will appear after the backend validates the ZIP batch.</p>
      )}

      <div className="score-placeholder">
        <span className="section-kicker">Scoring</span>
        {scoredTeams.length > 0 && latestScore ? (
          <>
            <div className="score-inline-grid">
              <div>
                <span>Scored</span>
                <strong>
                  {scoredTeams.length}/{executionResults.length}
                </strong>
              </div>
              <div>
                <span>Latest delta</span>
                <strong>{formatPoints(latestScore.total_delta, true)}</strong>
              </div>
              <div>
                <span>New total</span>
                <strong>{formatPoints(latestScore.new_total_points)}</strong>
              </div>
            </div>
            <p>Open Results for the FantasyXI roster, Risk Play outcome, and point breakdown.</p>
          </>
        ) : (
          <p>
            Final scores appear when the backend scoring route finishes FantasyXI validation, Risk Play resolution, and
            leaderboard impact.
          </p>
        )}
      </div>
    </aside>
  );
}
