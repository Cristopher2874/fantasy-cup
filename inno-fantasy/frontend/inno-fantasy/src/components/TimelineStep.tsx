import { TimelineState } from '../types';

type TimelineStepProps = {
  label: string;
  state: TimelineState;
};

export function TimelineStep({ label, state }: TimelineStepProps) {
  return (
    <div className={`timeline-step timeline-${state}`}>
      <span aria-hidden="true" />
      <p>{label}</p>
    </div>
  );
}
