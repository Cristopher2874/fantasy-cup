type BetaDisclaimerProps = {
  onDismiss: () => void;
};

export function BetaDisclaimer({ onDismiss }: BetaDisclaimerProps) {
  return (
    <aside className="beta-disclaimer-shell" aria-label="Beta app disclaimer">
      <div className="beta-disclaimer" role="status">
        <span className="beta-badge">Beta</span>
        <p>
          This is a beta app version for testing the skill flow: validate an uploaded skill, run it, and score the
          produced claim. The final version will be ready later this week with the actual functions and finalized rules.
        </p>
        <button className="beta-dismiss" type="button" onClick={onDismiss} aria-label="Dismiss beta disclaimer">
          Dismiss
        </button>
      </div>
    </aside>
  );
}
