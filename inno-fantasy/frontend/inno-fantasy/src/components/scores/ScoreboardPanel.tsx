import { useCallback, useEffect, useState } from 'react';
import { fetchScores } from '../../services/api';
import { ScoresResponse } from '../../types';
import { formatTimestamp } from '../../utils/formatters';
import { formatPoints, scoreTone } from '../../utils/scoreUtils';

export function ScoreboardPanel() {
  const [scoreboard, setScoreboard] = useState<ScoresResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadScores = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      setScoreboard(await fetchScores());
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : 'Could not load scores.');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadScores();
  }, [loadScores]);

  const teams = scoreboard?.leaderboard.teams ?? [];
  const recentScores = scoreboard?.scores ?? [];

  return (
    <section className="scoreboard-panel" aria-label="Scoring overview">
      <div className="scoreboard-heading">
        <div>
          <span className="section-kicker">Scoring overview</span>
          <h2>Leaderboard and scored runs</h2>
        </div>
        <button className="button button-secondary compact-button" type="button" onClick={loadScores} disabled={isLoading}>
          {isLoading ? 'Loading...' : 'Refresh scores'}
        </button>
      </div>

      {error && <div className="alert alert-warning">{error}</div>}

      <div className="scoreboard-grid">
        <div className="scoreboard-card">
          <h3>Current leaderboard</h3>
          {teams.length > 0 ? (
            <div className="score-table-wrap">
              <table className="score-table">
                <thead>
                  <tr>
                    <th>Rank</th>
                    <th>Team</th>
                    <th>Total</th>
                    <th>Fantasy</th>
                    <th>Risk</th>
                  </tr>
                </thead>
                <tbody>
                  {teams.slice(0, 6).map((team) => (
                    <tr key={team.team_id}>
                      <td>{team.rank ?? '-'}</td>
                      <td>{team.team_name}</td>
                      <td>{formatPoints(team.total_points)}</td>
                      <td>{formatPoints(team.fantasy_points)}</td>
                      <td>{formatPoints(team.risk_points, true)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="muted-text">No teams have been scored yet.</p>
          )}
        </div>

        <div className="scoreboard-card">
          <h3>Recent scored runs</h3>
          {recentScores.length > 0 ? (
            <ul className="recent-score-list">
              {recentScores.slice(0, 5).map((score) => (
                <li key={score.job_id}>
                  <div>
                    <strong>{score.result.team_name}</strong>
                    <span>{score.generated_at ? formatTimestamp(score.generated_at) : score.job_id}</span>
                  </div>
                  <span className={`status-pill ${scoreTone(score.result.status)}`}>{formatPoints(score.result.total_delta, true)}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="muted-text">Scored runs will appear after the backend writes score results.</p>
          )}
        </div>
      </div>
    </section>
  );
}
