import { FormEvent, useEffect, useMemo, useRef, useState } from 'react';
import './App.css';

type View = 'home' | 'about' | 'submit';

type ValidationResult = {
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

type UploadResponse = {
  job_id: string;
  team_id?: string | null;
  status: string;
  accepted: number;
  rejected: number;
  execution_status?: string;
  results: ValidationResult[];
};

type RunnerResult = {
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

type PipelineJob = {
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

type FileCheck = {
  file: File;
  ok: boolean;
  issue?: string;
};

const MAX_UPLOADS = 5;
const MAX_ZIP_BYTES = 5 * 1024 * 1024;

const navigation: Array<{ view: View; label: string }> = [
  { view: 'home', label: 'Home' },
  { view: 'about', label: 'About' },
  { view: 'submit', label: 'Submit' },
];

const scoringRows = [
  ['Player starts', '+2'],
  ['Plays 60+ minutes', '+2'],
  ['Goal', '+6'],
  ['Assist', '+4'],
  ['Defender or goalkeeper clean sheet', '+4'],
  ['Goalkeeper makes 3+ saves', '+2'],
  ['Yellow card', '-1'],
  ['Red card or own goal', '-3'],
];

const riskRows = [
  ['Green', '15%', 'Safer match outcome claims'],
  ['Yellow', '25%', 'Specific medium-risk claims'],
  ['Red', '35%', 'Bold claims with large swings'],
];

const packageRules = [
  'Upload ZIP files only.',
  'Submit up to five skills in one batch.',
  'Each ZIP must be 5 MB or smaller.',
  'Each skill needs exactly one SKILL.md file.',
  'Allowed top-level entries are SKILL.md, agents, references, and assets.',
  'Scripts, executable files, secrets, private keys, and tokens are rejected.',
];

function App() {
  const [activeView, setActiveView] = useState<View>('home');
  const [teamId, setTeamId] = useState('');
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [uploadResponse, setUploadResponse] = useState<UploadResponse | null>(null);
  const [progressJobs, setProgressJobs] = useState<Record<string, PipelineJob>>({});
  const [recentJobs, setRecentJobs] = useState<PipelineJob[]>([]);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [streamAlerts, setStreamAlerts] = useState<Record<string, string>>({});
  const streamRefs = useRef<Record<string, EventSource>>({});

  useEffect(() => {
    return () => {
      Object.values(streamRefs.current).forEach((source) => source.close());
    };
  }, []);

  const fileChecks = useMemo(
    () =>
      selectedFiles.map((file): FileCheck => {
        if (!file.name.toLowerCase().endsWith('.zip')) {
          return { file, ok: false, issue: 'File must use the .zip extension.' };
        }
        if (file.size > MAX_ZIP_BYTES) {
          return { file, ok: false, issue: 'File is larger than 5 MB.' };
        }
        return { file, ok: true };
      }),
    [selectedFiles],
  );

  const hasClientIssues = fileChecks.some((check) => !check.ok);
  const acceptedResults = uploadResponse?.results.filter((result) => result.valid) ?? [];
  const rejectedResults = uploadResponse?.results.filter((result) => !result.valid) ?? [];
  const executionResults = uploadResponse?.results.filter((result) => result.execution_job_id) ?? [];

  const closeStreams = () => {
    Object.values(streamRefs.current).forEach((source) => source.close());
    streamRefs.current = {};
  };

  const connectToProgress = (jobId: string) => {
    if (streamRefs.current[jobId]) {
      return;
    }

    try {
      const source = new EventSource(`/progress/${jobId}/stream`);
      streamRefs.current[jobId] = source;

      source.addEventListener('progress', (event) => {
        const message = event as MessageEvent<string>;
        const job = JSON.parse(message.data) as PipelineJob;
        setProgressJobs((current) => ({ ...current, [jobId]: job }));
        setStreamAlerts((current) => {
          const next = { ...current };
          delete next[jobId];
          return next;
        });

        if (job.status === 'completed' || job.status === 'failed' || job.status === 'missing') {
          source.close();
          delete streamRefs.current[jobId];
        }
      });

      source.onerror = () => {
        source.close();
        delete streamRefs.current[jobId];
        setStreamAlerts((current) => ({
          ...current,
          [jobId]: 'Live updates paused. Refresh execution jobs to poll the server.',
        }));
      };
    } catch {
      setStreamAlerts((current) => ({
        ...current,
        [jobId]: 'This browser could not open the live progress stream.',
      }));
    }
  };

  const handleFiles = (files: FileList | File[]) => {
    const incoming = Array.from(files);
    const limited = incoming.slice(0, MAX_UPLOADS);
    setSelectedFiles(limited);
    setSubmitError(incoming.length > MAX_UPLOADS ? `Only the first ${MAX_UPLOADS} ZIP files were selected.` : null);
    setUploadResponse(null);
    setProgressJobs({});
    setStreamAlerts({});
    closeStreams();
  };

  const removeFile = (index: number) => {
    setSelectedFiles((current) => current.filter((_, currentIndex) => currentIndex !== index));
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSubmitError(null);

    if (selectedFiles.length === 0) {
      setSubmitError('Select at least one skill ZIP before submitting.');
      return;
    }

    if (hasClientIssues) {
      setSubmitError('Fix the file checks before sending this batch.');
      return;
    }

    setIsSubmitting(true);
    setUploadResponse(null);
    setProgressJobs({});
    setStreamAlerts({});
    closeStreams();

    const formData = new FormData();
    selectedFiles.forEach((file) => formData.append('files', file));
    if (teamId.trim()) {
      formData.append('team_id', teamId.trim());
    }

    try {
      const response = await fetch('/upload', {
        method: 'POST',
        body: formData,
      });
      const payload = await parseResponse(response);

      if (!response.ok) {
        throw new Error(formatApiError(payload));
      }

      const uploadPayload = payload as UploadResponse;
      setUploadResponse(uploadPayload);

      const seededJobs = uploadPayload.results.reduce<Record<string, PipelineJob>>((jobs, result) => {
        if (!result.execution_job_id) {
          return jobs;
        }

        jobs[result.execution_job_id] = {
          job_id: result.execution_job_id,
          validation_job_id: result.job_id,
          team_id: uploadPayload.team_id,
          skill_name: result.skill_name,
          filename: result.filename,
          status: result.execution_status ?? 'queued',
          stage: 'queued',
          message: 'Skill is queued for execution.',
          issues: [],
          warnings: result.warnings ?? [],
        };
        return jobs;
      }, {});
      setProgressJobs(seededJobs);
      Object.keys(seededJobs).forEach(connectToProgress);
    } catch (error) {
      setSubmitError(error instanceof Error ? error.message : 'Upload failed.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const refreshJobs = async () => {
    setSubmitError(null);
    try {
      const response = await fetch('/progress');
      const payload = await parseResponse(response);
      if (!response.ok) {
        throw new Error(formatApiError(payload));
      }
      const jobs = Array.isArray(payload.jobs) ? (payload.jobs as PipelineJob[]) : [];
      setRecentJobs(jobs);
      setProgressJobs((current) => {
        const next = { ...current };
        jobs.forEach((job) => {
          next[job.job_id] = job;
        });
        return next;
      });
    } catch (error) {
      setSubmitError(error instanceof Error ? error.message : 'Could not load execution jobs.');
    }
  };

  return (
    <div className="app-shell">
      <header className="topbar">
        <button className="brand-lockup" type="button" onClick={() => setActiveView('home')}>
          <span className="brand-mark" aria-hidden="true">
            IF
          </span>
          <span>
            <span className="brand-eyebrow">Oracle AI fantasy lab</span>
            <span className="brand-name">Inno Fantasy Cup</span>
          </span>
        </button>

        <nav className="primary-nav" aria-label="Primary navigation">
          {navigation.map((item) => (
            <button
              className={item.view === activeView ? 'nav-link nav-link-active' : 'nav-link'}
              type="button"
              key={item.view}
              aria-current={item.view === activeView ? 'page' : undefined}
              onClick={() => setActiveView(item.view)}
            >
              {item.label}
            </button>
          ))}
        </nav>
      </header>

      <main>
        {activeView === 'home' && <HomePage onNavigate={setActiveView} />}
        {activeView === 'about' && <AboutPage onNavigate={setActiveView} />}
        {activeView === 'submit' && (
          <SubmitPage
            acceptedResults={acceptedResults}
            executionResults={executionResults}
            fileChecks={fileChecks}
            hasClientIssues={hasClientIssues}
            isDragging={isDragging}
            isSubmitting={isSubmitting}
            progressJobs={progressJobs}
            recentJobs={recentJobs}
            rejectedResults={rejectedResults}
            selectedFiles={selectedFiles}
            streamAlerts={streamAlerts}
            submitError={submitError}
            teamId={teamId}
            uploadResponse={uploadResponse}
            onDrop={(files) => handleFiles(files)}
            onFileInput={(files) => handleFiles(files)}
            onRefreshJobs={refreshJobs}
            onRemoveFile={removeFile}
            onSetDragging={setIsDragging}
            onSubmit={handleSubmit}
            onTeamIdChange={setTeamId}
          />
        )}
      </main>
    </div>
  );
}

type HomeProps = {
  onNavigate: (view: View) => void;
};

function HomePage({ onNavigate }: HomeProps) {
  return (
    <>
      <section className="hero-band">
        <div className="hero-content">
          <div className="hero-copy">
            <span className="section-kicker">Matchday skill operations</span>
            <h1>Submit an AI skill, validate the package, and watch the run move toward scoring.</h1>
            <p>
              The first release focuses on a tight tournament loop: teams upload skill ZIPs, the backend validates
              them, accepted snapshots execute in isolation, and the app keeps the team informed until the result is
              ready for scoring.
            </p>
            <div className="hero-actions">
              <button className="button button-primary" type="button" onClick={() => onNavigate('submit')}>
                Submit skill
              </button>
              <button className="button button-secondary" type="button" onClick={() => onNavigate('about')}>
                Review rules
              </button>
            </div>
          </div>

          <div className="matchday-visual" aria-label="Fantasy Cup run stages">
            <div className="pitch-grid">
              {['GK', 'DEF', 'DEF', 'MID', 'MID', 'MID', 'FWD', 'Risk', 'JSON'].map((label, index) => (
                <span key={`${label}-${index}`}>{label}</span>
              ))}
            </div>
            <div className="run-strip">
              <span>Validate</span>
              <span>Snapshot</span>
              <span>Execute</span>
              <span>Score</span>
            </div>
          </div>
        </div>
      </section>

      <section className="content-band">
        <div className="dashboard-grid">
          <article className="metric-card">
            <span className="metric-label">Team size</span>
            <strong>1-10</strong>
            <p>Teams submit decision-making skills instead of manual daily picks.</p>
          </article>
          <article className="metric-card">
            <span className="metric-label">Fantasy XI</span>
            <strong>11</strong>
            <p>Agents must return valid player records from the official matchday data.</p>
          </article>
          <article className="metric-card">
            <span className="metric-label">Risk tiers</span>
            <strong>3</strong>
            <p>Green, Yellow, and Red claims change the score by a percentage stake.</p>
          </article>
          <article className="metric-card">
            <span className="metric-label">Current UI scope</span>
            <strong>V1</strong>
            <p>Home, rules, submission, validation feedback, and execution progress.</p>
          </article>
        </div>
      </section>

      <section className="content-band light-band">
        <div className="two-column">
          <div>
            <span className="section-kicker">Product boundary</span>
            <h2>Built for AI-driven fantasy decisions</h2>
            <p>
              This is not a transfer-market fantasy app. The core experience is a tournament automation platform where
              teams improve their agent skills and the app validates, runs, scores, and publishes the outcomes.
            </p>
          </div>
          <div className="process-list" aria-label="Tournament process">
            {['Official matchday data is approved', 'Skill package is refreshed after cutoff', 'Accepted snapshot runs alone', 'JSON answer is validated', 'Scores update after real match events'].map(
              (step, index) => (
                <div className="process-row" key={step}>
                  <span>{index + 1}</span>
                  <p>{step}</p>
                </div>
              ),
            )}
          </div>
        </div>
      </section>
    </>
  );
}

type AboutProps = {
  onNavigate: (view: View) => void;
};

function AboutPage({ onNavigate }: AboutProps) {
  return (
    <>
      <section className="page-header">
        <div>
          <span className="section-kicker">Draft participant guide</span>
          <h1>Rules, scoring, and submission shape</h1>
        </div>
        <button className="button button-primary" type="button" onClick={() => onNavigate('submit')}>
          Start a submission
        </button>
      </section>

      <section className="content-band">
        <div className="rules-grid">
          <article className="info-card wide-card">
            <h2>Matchday answers</h2>
            <p>
              During league play, each accepted skill produces a Fantasy XI, one optional Risk Play claim, and a short
              strategy summary. Knockout rounds add bracket picks that lock before the knockout cutoff.
            </p>
            <div className="answer-contract">
              <code>answers.fantasy_xi</code>
              <code>answers.risk_play</code>
              <code>answers.strategy_summary</code>
            </div>
          </article>

          <article className="info-card">
            <h2>Fantasy XI shape</h2>
            <ul className="clean-list">
              <li>Exactly 11 eligible player IDs.</li>
              <li>1 goalkeeper.</li>
              <li>3 to 5 defenders.</li>
              <li>3 to 5 midfielders.</li>
              <li>1 to 3 forwards.</li>
            </ul>
          </article>

          <article className="info-card">
            <h2>Failure policy</h2>
            <ul className="clean-list">
              <li>Invalid Risk Play can fall back to no Risk Play.</li>
              <li>Missing Fantasy XI may reuse the latest valid XI if allowed.</li>
              <li>Organizer scoring decisions are final after review.</li>
            </ul>
          </article>
        </div>
      </section>

      <section className="content-band light-band">
        <div className="table-wrap">
          <div>
            <span className="section-kicker">Points model</span>
            <h2>Fantasy XI scoring</h2>
          </div>
          <table>
            <thead>
              <tr>
                <th>Event</th>
                <th>Points</th>
              </tr>
            </thead>
            <tbody>
              {scoringRows.map(([event, points]) => (
                <tr key={event}>
                  <td>{event}</td>
                  <td>{points}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="content-band">
        <div className="rules-grid">
          <article className="info-card wide-card">
            <h2>Risk Play stakes</h2>
            <div className="risk-grid">
              {riskRows.map(([tier, stake, description]) => (
                <div className={`risk-chip risk-${tier.toLowerCase()}`} key={tier}>
                  <span>{tier}</span>
                  <strong>{stake}</strong>
                  <p>{description}</p>
                </div>
              ))}
            </div>
          </article>

          <article className="info-card wide-card">
            <h2>Skill package guardrails</h2>
            <ul className="clean-list compact-list">
              {packageRules.map((rule) => (
                <li key={rule}>{rule}</li>
              ))}
            </ul>
          </article>
        </div>
      </section>
    </>
  );
}

type SubmitProps = {
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
  onDrop: (files: FileList) => void;
  onFileInput: (files: FileList) => void;
  onRefreshJobs: () => void;
  onRemoveFile: (index: number) => void;
  onSetDragging: (value: boolean) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  onTeamIdChange: (value: string) => void;
};

function SubmitPage({
  acceptedResults,
  executionResults,
  fileChecks,
  hasClientIssues,
  isDragging,
  isSubmitting,
  progressJobs,
  recentJobs,
  rejectedResults,
  selectedFiles,
  streamAlerts,
  submitError,
  teamId,
  uploadResponse,
  onDrop,
  onFileInput,
  onRefreshJobs,
  onRemoveFile,
  onSetDragging,
  onSubmit,
  onTeamIdChange,
}: SubmitProps) {
  return (
    <>
      <section className="page-header">
        <div>
          <span className="section-kicker">Skill submission</span>
          <h1>Upload, validate, execute, and inspect the run state.</h1>
        </div>
        <button className="button button-secondary" type="button" onClick={onRefreshJobs}>
          Refresh execution jobs
        </button>
      </section>

      <section className="submit-layout">
        <form className="submission-panel" onSubmit={onSubmit}>
          <div className="field-group">
            <label htmlFor="teamId">Team ID</label>
            <input
              id="teamId"
              name="teamId"
              placeholder="optional-team-id"
              value={teamId}
              onChange={(event) => onTeamIdChange(event.target.value)}
            />
          </div>

          <div
            className={isDragging ? 'dropzone dropzone-active' : 'dropzone'}
            onDragOver={(event) => {
              event.preventDefault();
              onSetDragging(true);
            }}
            onDragLeave={() => onSetDragging(false)}
            onDrop={(event) => {
              event.preventDefault();
              onSetDragging(false);
              onDrop(event.dataTransfer.files);
            }}
          >
            <input
              id="skillFiles"
              type="file"
              accept=".zip,application/zip,application/x-zip-compressed"
              multiple
              onChange={(event) => {
                if (event.target.files) {
                  onFileInput(event.target.files);
                }
              }}
            />
            <label htmlFor="skillFiles">
              <strong>Drop skill ZIPs here</strong>
              <span>or browse for up to five files</span>
            </label>
          </div>

          <div className="preflight">
            <div className="panel-heading">
              <h2>Preflight checks</h2>
              <span className={hasClientIssues ? 'status-pill status-invalid' : 'status-pill status-valid'}>
                {selectedFiles.length === 0 ? 'Waiting' : hasClientIssues ? 'Needs attention' : 'Ready'}
              </span>
            </div>

            {selectedFiles.length === 0 ? (
              <p className="muted-text">No ZIP files selected.</p>
            ) : (
              <ul className="file-list">
                {fileChecks.map((check, index) => (
                  <li key={`${check.file.name}-${check.file.lastModified}`}>
                    <div>
                      <strong>{check.file.name}</strong>
                      <span>{formatFileSize(check.file.size)}</span>
                      {check.issue && <p>{check.issue}</p>}
                    </div>
                    <button className="text-button" type="button" onClick={() => onRemoveFile(index)}>
                      Remove
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>

          {submitError && <div className="alert alert-error">{submitError}</div>}

          <button className="button button-primary full-width" type="submit" disabled={isSubmitting || hasClientIssues}>
            {isSubmitting ? 'Submitting...' : 'Submit skill batch'}
          </button>
        </form>

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
      </section>

      {(uploadResponse || recentJobs.length > 0) && (
        <section className="content-band result-band">
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
                const job = jobId ? progressJobs[jobId] : undefined;

                return (
                  <article className="result-card" key={result.job_id}>
                    <div className="result-title">
                      <div>
                        <span className="filename">{result.filename}</span>
                        <h3>{result.skill_name ?? 'Skill package'}</h3>
                      </div>
                      <span className={`status-pill ${result.valid ? 'status-valid' : 'status-invalid'}`}>
                        {result.status}
                      </span>
                    </div>

                    <ResultMessages title="Issues" messages={result.issues ?? []} tone="error" />
                    <ResultMessages title="Warnings" messages={result.warnings ?? []} tone="warning" />

                    {jobId ? (
                      <ExecutionDetails job={job} jobId={jobId} streamAlert={streamAlerts[jobId]} />
                    ) : (
                      <p className="muted-text">This package did not enter execution.</p>
                    )}
                  </article>
                );
              })}
            </div>
          )}

          {!uploadResponse && recentJobs.length > 0 && (
            <div className="results-grid">
              {recentJobs.slice(0, 6).map((job) => (
                <article className="result-card" key={job.job_id}>
                  <div className="result-title">
                    <div>
                      <span className="filename">{job.filename ?? job.job_id}</span>
                      <h3>{job.skill_name ?? 'Execution job'}</h3>
                    </div>
                    <span className={`status-pill ${statusClass(job.status)}`}>{job.status}</span>
                  </div>
                  <ExecutionDetails job={job} jobId={job.job_id} streamAlert={streamAlerts[job.job_id]} />
                </article>
              ))}
            </div>
          )}
        </section>
      )}
    </>
  );
}

function TimelineStep({ label, state }: { label: string; state: 'idle' | 'active' | 'complete' | 'warning' }) {
  return (
    <div className={`timeline-step timeline-${state}`}>
      <span aria-hidden="true" />
      <p>{label}</p>
    </div>
  );
}

function ResultMessages({ title, messages, tone }: { title: string; messages: string[]; tone: 'error' | 'warning' }) {
  if (messages.length === 0) {
    return null;
  }

  return (
    <div className={`message-list message-${tone}`}>
      <strong>{title}</strong>
      <ul>
        {messages.map((message) => (
          <li key={message}>{message}</li>
        ))}
      </ul>
    </div>
  );
}

function ExecutionDetails({
  job,
  jobId,
  streamAlert,
}: {
  job?: PipelineJob;
  jobId: string;
  streamAlert?: string;
}) {
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

async function parseResponse(response: Response): Promise<Record<string, unknown>> {
  const text = await response.text();
  if (!text) {
    return {};
  }

  try {
    return JSON.parse(text) as Record<string, unknown>;
  } catch {
    return { detail: text };
  }
}

function formatApiError(payload: Record<string, unknown>): string {
  const detail = payload.detail;
  if (typeof detail === 'string') {
    return detail;
  }
  if (Array.isArray(detail)) {
    return detail.map(String).join(', ');
  }
  return 'The server rejected the request.';
}

function executionState(results: ValidationResult[], progressJobs: Record<string, PipelineJob>) {
  const jobs = results
    .map((result) => (result.execution_job_id ? progressJobs[result.execution_job_id] : undefined))
    .filter(Boolean) as PipelineJob[];

  if (jobs.length === 0) {
    return 'active' as const;
  }
  if (jobs.some((job) => job.status === 'failed')) {
    return 'warning' as const;
  }
  if (jobs.every((job) => job.status === 'completed')) {
    return 'complete' as const;
  }
  return 'active' as const;
}

function scoreState(results: ValidationResult[], progressJobs: Record<string, PipelineJob>) {
  const jobs = results
    .map((result) => (result.execution_job_id ? progressJobs[result.execution_job_id] : undefined))
    .filter(Boolean) as PipelineJob[];

  if (jobs.length > 0 && jobs.every((job) => job.status === 'completed')) {
    return 'active' as const;
  }
  return 'idle' as const;
}

function statusClass(status: string) {
  if (status === 'valid' || status === 'completed') {
    return 'status-valid';
  }
  if (status === 'invalid' || status === 'failed' || status === 'missing') {
    return 'status-invalid';
  }
  if (status === 'running' || status === 'queued') {
    return 'status-working';
  }
  return 'status-neutral';
}

function formatFileSize(bytes: number) {
  if (bytes < 1024) {
    return `${bytes} B`;
  }
  if (bytes < 1024 * 1024) {
    return `${(bytes / 1024).toFixed(1)} KB`;
  }
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatTimestamp(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(date);
}

export default App;
