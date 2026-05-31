import { useEffect, useMemo, useState } from 'react';
import { ResultMessages } from '../ResultMessages';
import { fetchScore } from '../../services/api';
import { PipelineJob, ScoreResult } from '../../types';
import { formatTimestamp } from '../../utils/formatters';
import { formatPoints, getScoreResult, scoreTone } from '../../utils/scoreUtils';

type ScoreResultPanelProps = {
  job?: PipelineJob;
  jobId: string;
};

export function ScoreResultPanel({ job, jobId }: ScoreResultPanelProps) {
  const [score, setScore] = useState<ScoreResult | null>(getScoreResult(job));
  const [scoreIssues, setScoreIssues] = useState<string[]>(job?.score?.issues ?? []);
  const [lookupError, setLookupError] = useState<string | null>(null);
  const [lookedUpJobId, setLookedUpJobId] = useState<string | null>(null);

  const isReadyForScoring =
    job?.status === 'completed' || job?.stage === 'scoring_failed' || Boolean(job?.runner?.submission_path);

  useEffect(() => {
    const pipelineScore = getScoreResult(job);
    if (pipelineScore) {
      setScore(pipelineScore);
    }
    setScoreIssues(job?.score?.issues ?? []);
  }, [job]);

  useEffect(() => {
    if (!isReadyForScoring || score || lookedUpJobId === jobId) {
      return;
    }

    let isActive = true;
    setLookedUpJobId(jobId);
    fetchScore(jobId)
      .then((storedScore) => {
        if (isActive && storedScore) {
          setScore(storedScore);
        }
      })
      .catch((error) => {
        if (isActive) {
          setLookupError(error instanceof Error ? error.message : 'Could not load stored score.');
        }
      });

    return () => {
      isActive = false;
    };
  }, [isReadyForScoring, jobId, lookedUpJobId, score]);

  const issues = useMemo(
    () => Array.from(new Set([...(scoreIssues ?? []), ...(job?.score?.issues ?? [])])),
    [job?.score?.issues, scoreIssues],
  );

  if (!score) {
    return (
      <section className="score-panel" aria-label="Score result">
        <div className="score-panel-header">
          <div>
            <span className="section-kicker">Final score</span>
            <h4>Awaiting scored output</h4>
          </div>
        </div>
        <p className="muted-text">
          {isReadyForScoring
            ? 'This run produced a submission JSON. Waiting for the automatic scoring result from the backend.'
            : 'The score appears here after execution reaches the backend scoring stage.'}
        </p>
        <ResultMessages title="Scoring issues" messages={issues} tone="error" />
        {lookupError && <div className="alert alert-warning">{lookupError}</div>}
      </section>
    );
  }

  const teamScore = score.result;
  const fantasy = teamScore.fantasy;
  const risk = teamScore.risk;
  const riskLabel = risk.outcome === 'skipped' ? 'Skipped' : risk.outcome;

  return (
    <section className="score-panel score-panel-ready" aria-label="Score result">
      <div className="score-panel-header">
        <div>
          <span className="section-kicker">Final score</span>
          <h4>{teamScore.team_name}</h4>
          <p>
            {score.matchday_id ?? 'Matchday'} scored {score.generated_at ? `at ${formatTimestamp(score.generated_at)}` : ''}
          </p>
        </div>
        <span className={`status-pill ${scoreTone(teamScore.status, fantasy.valid && risk.valid)}`}>{teamScore.status}</span>
      </div>

      <div className="score-metrics">
        <ScoreMetric label="Previous total" value={formatPoints(teamScore.previous_total_points)} />
        <ScoreMetric label="Fantasy XI" value={formatPoints(teamScore.fantasy_points, true)} />
        <ScoreMetric label="Risk Play" value={formatPoints(teamScore.risk_points, true)} />
        <ScoreMetric label="Matchday delta" value={formatPoints(teamScore.total_delta, true)} />
        <ScoreMetric label="New total" value={formatPoints(teamScore.new_total_points)} strong />
      </div>

      <div className="score-detail-grid">
        <details className="score-detail" open>
          <summary>
            Fantasy XI <span className={`status-pill ${scoreTone(undefined, fantasy.valid)}`}>{fantasy.valid ? 'valid' : 'invalid'}</span>
          </summary>
          <div className="position-counts">
            {Object.entries(fantasy.position_counts ?? {}).map(([position, count]) => (
              <span key={position}>
                {position} <strong>{count}</strong>
              </span>
            ))}
          </div>
          <ResultMessages title="Fantasy XI errors" messages={fantasy.errors ?? []} tone="error" />
          <ResultMessages title="Fantasy XI warnings" messages={fantasy.warnings ?? []} tone="warning" />
          {fantasy.players.length > 0 && (
            <div className="score-table-wrap">
              <table className="score-table">
                <thead>
                  <tr>
                    <th>Player</th>
                    <th>Position</th>
                    <th>Team</th>
                    <th>Points</th>
                  </tr>
                </thead>
                <tbody>
                  {fantasy.players.map((player) => (
                    <tr key={player.record_id}>
                      <td>{player.name}</td>
                      <td>{player.position}</td>
                      <td>{player.team}</td>
                      <td>{formatPoints(player.points)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </details>

        <details className="score-detail" open>
          <summary>
            Risk Play <span className={`status-pill ${scoreTone(risk.outcome, risk.valid)}`}>{riskLabel}</span>
          </summary>
          <dl className="risk-summary">
            <div>
              <dt>Claim</dt>
              <dd>{risk.claim_id ?? 'No claim submitted'}</dd>
            </div>
            <div>
              <dt>Category</dt>
              <dd>{risk.category ?? 'n/a'}</dd>
            </div>
            <div>
              <dt>Stake</dt>
              <dd>{formatPoints(risk.stake)}</dd>
            </div>
            <div>
              <dt>Risk points</dt>
              <dd>{formatPoints(risk.points, true)}</dd>
            </div>
            {risk.evidence_path && (
              <div>
                <dt>Evidence</dt>
                <dd>{risk.evidence_path}</dd>
              </div>
            )}
          </dl>
          <ResultMessages title="Risk Play errors" messages={risk.errors ?? []} tone="error" />
          <ResultMessages title="Risk Play warnings" messages={risk.warnings ?? []} tone="warning" />
        </details>
      </div>
    </section>
  );
}

type ScoreMetricProps = {
  label: string;
  value: string;
  strong?: boolean;
};

function ScoreMetric({ label, value, strong }: ScoreMetricProps) {
  return (
    <div className={strong ? 'score-metric score-metric-strong' : 'score-metric'}>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}
