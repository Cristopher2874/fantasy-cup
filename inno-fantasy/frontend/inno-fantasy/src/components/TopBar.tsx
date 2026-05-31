import { navigation } from '../data/appContent';
import { View } from '../types';

type TopBarProps = {
  activeView: View;
  onNavigate: (view: View) => void;
};

export function TopBar({ activeView, onNavigate }: TopBarProps) {
  return (
    <header className="topbar">
      <button className="brand-lockup" type="button" onClick={() => onNavigate('home')}>
        <span className="brand-mark" aria-hidden="true">
          IF
        </span>
        <span>
          <span className="brand-eyebrow">InnovationLab</span>
          <span className="brand-name">FantasyXI</span>
        </span>
      </button>

      <nav className="primary-nav" aria-label="Primary navigation">
        {navigation.map((item) => (
          <button
            className={item.view === activeView ? 'nav-link nav-link-active' : 'nav-link'}
            type="button"
            key={item.view}
            aria-current={item.view === activeView ? 'page' : undefined}
            onClick={() => onNavigate(item.view)}
          >
            {item.label}
          </button>
        ))}
      </nav>
    </header>
  );
}
