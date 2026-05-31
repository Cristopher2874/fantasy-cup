import { pitchMarkers, tournamentProcessSteps } from '../data/appContent';
import { View } from '../types';

type HomePageProps = {
  onNavigate: (view: View) => void;
};

export function HomePage({ onNavigate }: HomePageProps) {
  return (
    <>
      <section className="hero-band">
        <div className="hero-content">
          <div className="hero-copy">
            <span className="section-kicker">InnovationLab</span>
            <h1>FantasyXI skill operations for matchday decisions.</h1>
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

          <div className="matchday-visual" aria-label="FantasyXI run stages">
            <div className="pitch-grid">
              {pitchMarkers.map((label, index) => (
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
            <span className="metric-label">FantasyXI</span>
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
            {tournamentProcessSteps.map((step, index) => (
              <div className="process-row" key={step}>
                <span>{index + 1}</span>
                <p>{step}</p>
              </div>
            ))}
          </div>
        </div>
      </section>
    </>
  );
}
