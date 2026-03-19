import React from 'react';

export default function Layout({ page, setPage, children }: any) {
  const tabs = ['Overview', 'Candidates', 'Positions', 'Decisions', 'Settings'];
  return (
    <div style={{ maxWidth: 1200, margin: '0 auto', padding: 16 }}>
      <h1>KrakBot AI Trading Lab</h1>
      <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
        {tabs.map(t => <button key={t} onClick={() => setPage(t)} style={{ fontWeight: page===t ? 700 : 400 }}>{t}</button>)}
      </div>
      {children}
    </div>
  );
}
