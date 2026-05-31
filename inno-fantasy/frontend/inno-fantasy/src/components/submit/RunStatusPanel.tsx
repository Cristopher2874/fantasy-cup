import { TimelineStep } from '../TimelineStep';
import { PipelineJob, UploadResponse, ValidationResult } from '../../types';
import { executionState, scoreState } from '../../utils/pipelineState';

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
        <p>
          Scoring is reserved for the next backend phase. Once scores are published, this panel can show matchday
          points, Risk Play delta, and final standing impact.
        </p>
      </div>
    </aside>
  );
}
