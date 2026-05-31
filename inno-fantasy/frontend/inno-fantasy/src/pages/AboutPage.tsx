import {
  answerFormatRules,
  packageRules,
  playerSelectionRules,
  riskClaimRows,
  riskRows,
  riskSelectionRules,
  scoringRows,
} from '../data/appContent';
import { View } from '../types';

type AboutPageProps = {
  onNavigate: (view: View) => void;
};

export function AboutPage({ onNavigate }: AboutPageProps) {
  return (
    <>
      <section className="page-header">
        <div>
          <span className="section-kicker">InnovationLab</span>
          <h1>FantasyXI rules reference</h1>
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
              During league play, each accepted skill produces a FantasyXI, one optional Risk Play claim, and a short
              strategy summary. Knockout rounds add bracket picks that lock before the knockout cutoff.
            </p>
            <div className="answer-contract">
              <code>answers.fantasy_xi</code>
              <code>answers.risk_play</code>
              <code>answers.strategy_summary</code>
            </div>
          </article>

          <article className="info-card">
            <h2>FantasyXI shape</h2>
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
              <li>Missing FantasyXI may reuse the latest valid XI if allowed.</li>
              <li>Organizer scoring decisions are final after review.</li>
            </ul>
          </article>
        </div>
      </section>

      <section className="content-band light-band">
        <div className="table-wrap">
          <div>
            <span className="section-kicker">Points model</span>
            <h2>FantasyXI scoring</h2>
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
            <h2>How players are selected</h2>
            <ul className="clean-list compact-list">
              {playerSelectionRules.map((rule) => (
                <li key={rule}>{rule}</li>
              ))}
            </ul>
          </article>

          <article className="info-card wide-card">
            <h2>Expected answer format</h2>
            <ul className="clean-list compact-list">
              {answerFormatRules.map((rule) => (
                <li key={rule}>{rule}</li>
              ))}
            </ul>
          </article>

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
            <h2>Risk Play rules</h2>
            <ul className="clean-list compact-list">
              {riskSelectionRules.map((rule) => (
                <li key={rule}>{rule}</li>
              ))}
            </ul>
          </article>

          <article className="info-card wide-card">
            <h2>Available Risk Play claim types</h2>
            <div className="reference-table-wrap">
              <table className="reference-table">
                <thead>
                  <tr>
                    <th>Claim ID</th>
                    <th>Tier</th>
                    <th>Required fields</th>
                    <th>Outcome</th>
                  </tr>
                </thead>
                <tbody>
                  {riskClaimRows.map(([claimId, tier, fields, outcome]) => (
                    <tr key={claimId}>
                      <td>
                        <code>{claimId}</code>
                      </td>
                      <td>{tier}</td>
                      <td>{fields}</td>
                      <td>{outcome}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </article>

          <article className="info-card wide-card">
            <h2>Upload validation requirements</h2>
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
