import { useEffect, useState } from 'react';
import { ResultsSection } from '../components/submit/ResultsSection';
import { RunStatusPanel } from '../components/submit/RunStatusPanel';
import { SubmissionForm } from '../components/submit/SubmissionForm';
import { useSkillSubmission } from '../hooks/useSkillSubmission';
import { SubmitTab } from '../types';

const submitTabs: Array<{ id: SubmitTab; label: string }> = [
  { id: 'upload', label: 'Upload' },
  { id: 'jobs', label: 'Jobs' },
  { id: 'results', label: 'Results' },
];

export function SubmitPage() {
  const [activeTab, setActiveTab] = useState<SubmitTab>('upload');
  const submission = useSkillSubmission();

  useEffect(() => {
    if (!submission.uploadResponse) {
      return;
    }

    setActiveTab(submission.executionResults.length > 0 ? 'jobs' : 'results');
  }, [submission.executionResults.length, submission.uploadResponse]);

  const handleSubmit = (event: Parameters<typeof submission.handleSubmit>[0]) => {
    submission.handleSubmit(event);
    setActiveTab('jobs');
  };

  const handleRefreshJobs = async () => {
    await submission.refreshJobs();
    setActiveTab('jobs');
  };

  return (
    <>
      <section className="page-header submit-header">
        <div>
          <span className="section-kicker">Skill submission</span>
          <h1>Upload, validate, execute, and inspect the run state.</h1>
        </div>
        <button className="button button-secondary" type="button" onClick={handleRefreshJobs}>
          Refresh execution jobs
        </button>
      </section>

      <section className="submission-workspace">
        <div className="workspace-tabs" role="tablist" aria-label="Submission workspace">
          {submitTabs.map((tab) => (
            <button
              className={activeTab === tab.id ? 'workspace-tab workspace-tab-active' : 'workspace-tab'}
              key={tab.id}
              type="button"
              role="tab"
              aria-selected={activeTab === tab.id}
              onClick={() => setActiveTab(tab.id)}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {activeTab === 'upload' && (
          <section className="submit-layout tab-panel" role="tabpanel">
            <SubmissionForm
              fileChecks={submission.fileChecks}
              hasClientIssues={submission.hasClientIssues}
              isDragging={submission.isDragging}
              isSubmitting={submission.isSubmitting}
              selectedFiles={submission.selectedFiles}
              submitError={submission.submitError}
              teamId={submission.teamId}
              onDrop={submission.handleFiles}
              onFileInput={submission.handleFiles}
              onRemoveFile={submission.removeFile}
              onSetDragging={submission.setIsDragging}
              onSubmit={handleSubmit}
              onTeamIdChange={submission.setTeamId}
            />
            <RunStatusPanel
              acceptedResults={submission.acceptedResults}
              executionResults={submission.executionResults}
              isSubmitting={submission.isSubmitting}
              progressJobs={submission.progressJobs}
              rejectedResults={submission.rejectedResults}
              uploadResponse={submission.uploadResponse}
            />
          </section>
        )}

        {activeTab === 'jobs' && (
          <section className="tab-panel compact-panel" role="tabpanel">
            <RunStatusPanel
              acceptedResults={submission.acceptedResults}
              executionResults={submission.executionResults}
              isSubmitting={submission.isSubmitting}
              progressJobs={submission.progressJobs}
              rejectedResults={submission.rejectedResults}
              uploadResponse={submission.uploadResponse}
            />
          </section>
        )}

        {activeTab === 'results' && (
          <section className="tab-panel" role="tabpanel">
            <ResultsSection
              progressJobs={submission.progressJobs}
              recentJobs={submission.recentJobs}
              streamAlerts={submission.streamAlerts}
              uploadResponse={submission.uploadResponse}
            />
          </section>
        )}
      </section>
    </>
  );
}
