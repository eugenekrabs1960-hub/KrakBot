import { ReactNode } from 'react';

export type NavItem = { id: string; label: string };

type Props = {
  nav: NavItem[];
  active: string;
  onChange: (id: string) => void;
  children: ReactNode;
};

export default function AppShell({ nav, active, onChange, children }: Props) {
  const activeLabel = nav.find((n) => n.id === active)?.label || 'View';

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">KrakBot Operator UI</div>
        <div className="mobile-topbar">
          <strong>{activeLabel}</strong>
          <div className="mobile-topbar-actions">
            <button className="btn" onClick={() => onChange('overview')}>Overview</button>
            <button className="btn" onClick={() => onChange('controls')}>Controls</button>
          </div>
        </div>
        <div className="nav-row">
          {nav.map((item) => (
            <button key={item.id} className={`nav-btn ${active === item.id ? 'active' : ''}`} onClick={() => onChange(item.id)}>
              {item.label}
            </button>
          ))}
        </div>
      </aside>
      <div className="content">{children}</div>
    </div>
  );
}
