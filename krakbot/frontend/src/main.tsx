import React, { useEffect, useState } from 'react';
import ReactDOM from 'react-dom/client';
import './styles/tokens.css';
import './styles/app.css';

type CycleLog = any;

function App() {
  const [health, setHealth] = useState<any>(null);
  const [state, setState] = useState<any>(null);
  const [logs, setLogs] = useState<CycleLog[]>([]);
  const [symbol, setSymbol] = useState('BTC');
  const [busy, setBusy] = useState(false);

  const refresh = async () => {
    const [h, s, l] = await Promise.all([
      fetch('/api/lab/health').then(r => r.json()),
      fetch('/api/lab/state').then(r => r.json()),
      fetch('/api/lab/logs?limit=20').then(r => r.json()),
    ]);
    setHealth(h);
    setState(s);
    setLogs(l.items || []);
  };

  useEffect(() => { refresh(); }, []);

  const runCycle = async () => {
    setBusy(true);
    await fetch('/api/lab/cycle/run-once', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ symbol }),
    });
    await refresh();
    setBusy(false);
  };

  const switchMode = async (execution_mode: 'paper' | 'live_hyperliquid', live_armed = false) => {
    setBusy(true);
    await fetch('/api/lab/mode', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ execution_mode, live_armed }),
    });
    await refresh();
    setBusy(false);
  };

  return (
    <div style={{ maxWidth: 1100, margin: '24px auto', padding: 16 }}>
      <h1>KrakBot AI Trading Lab</h1>
      <p className="muted">Focused Hyperliquid futures lab: deterministic packet -> analyst -> policy gate -> broker.</p>

      <div className="card" style={{ marginBottom: 12 }}>
        <h3>Mode</h3>
        <div>Current: <b>{state?.mode?.execution_mode || '-'}</b> | Live armed: <b>{String(state?.mode?.live_armed ?? false)}</b></div>
        <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
          <button disabled={busy} onClick={() => switchMode('paper', false)}>Paper</button>
          <button disabled={busy} onClick={() => switchMode('live_hyperliquid', false)}>Live (disarmed)</button>
          <button disabled={busy} onClick={() => switchMode('live_hyperliquid', true)}>Live (armed)</button>
        </div>
      </div>

      <div className="card" style={{ marginBottom: 12 }}>
        <h3>Run Decision Cycle</h3>
        <div style={{ display: 'flex', gap: 8 }}>
          <input value={symbol} onChange={e => setSymbol(e.target.value.toUpperCase())} placeholder="BTC" />
          <button disabled={busy} onClick={runCycle}>Run once</button>
          <button disabled={busy} onClick={refresh}>Refresh</button>
        </div>
      </div>

      <div className="card" style={{ marginBottom: 12 }}>
        <h3>System</h3>
        <pre>{JSON.stringify({ health, mode: state?.mode, paper_positions: state?.paper_positions }, null, 2)}</pre>
      </div>

      <div className="card">
        <h3>Recent Cycles</h3>
        <pre style={{ maxHeight: 420, overflow: 'auto' }}>{JSON.stringify(logs, null, 2)}</pre>
      </div>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
