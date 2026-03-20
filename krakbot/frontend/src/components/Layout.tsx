import React from 'react';

export default function Layout({ page, setPage, children }: any) {
  const tabs = ['Overview', 'Candidates', 'Positions', 'Decisions', 'Experiments', 'Settings'];
  return (
    <div style={{ maxWidth: 1200, margin: '0 auto', padding: 16 }}>
      <h1>KrakBot AI Trading Lab</h1>
      <div className="top-tabs" role="tablist" aria-label="Main navigation">
        {tabs.map((t) => (
          <button
            key={t}
            onClick={() => setPage(t)}
            className={`top-tab ${page === t ? 'active' : ''}`}
            role="tab"
            aria-selected={page === t}
          >
            {t}
          </button>
        ))}
      </div>
      {children}
    </div>
  );
}
