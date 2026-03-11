import { useEffect, useState } from 'react';
import PageHeader from '../components/PageHeader';
import {
  getActivePaperModel,
  getAgentDecisionPackets,
  getLatestModel,
  getModelLabJobHistory,
  getStrategyBenchmarks,
  getWalletCohortLatest,
  promoteModelToPaper,
  trainBaselineModel,
} from '../services/api';

export default function ModelLab() {
  const [symbol, setSymbol] = useState('BTC');
  const [bench, setBench] = useState<any[]>([]);
  const [model, setModel] = useState<any>(null);
  const [wallets, setWallets] = useState<any[]>([]);
  const [jobs, setJobs] = useState<any[]>([]);
  const [packets, setPackets] = useState<any[]>([]);
  const [activePaper, setActivePaper] = useState<any>(null);
  const [msg, setMsg] = useState('');
  const [busy, setBusy] = useState(false);
  const [confirm, setConfirm] = useState('');

  const load = async () => {
    const [b, m, w, j, p, ap] = await Promise.all([
      getStrategyBenchmarks(symbol, 50000).catch(() => ({ items: [] })),
      getLatestModel(symbol).catch(() => null),
      getWalletCohortLatest('top_sol_active_wallets').catch(() => ({ members: [] })),
      getModelLabJobHistory(20).catch(() => ({ items: [] })),
      getAgentDecisionPackets(20, undefined, symbol).catch(() => ({ items: [] })),
      getActivePaperModel().catch(() => ({ item: null })),
    ]);
    setBench(b?.items || []);
    setModel(m?.item ? { ...m.item, path: m.path } : null);
    setWallets((w?.members || []).slice(0, 10));
    setJobs(j?.items || []);
    setPackets(p?.items || []);
    setActivePaper(ap?.item || null);
  };

  useEffect(() => {
    load();
  }, [symbol]);

  async function trainNow() {
    setBusy(true);
    setMsg('');
    try {
      const out = await trainBaselineModel(symbol, 50000);
      if (out?.ok) {
        setMsg(`Training complete. Accuracy ${(Number(out?.metrics?.accuracy || 0) * 100).toFixed(1)}%`);
      } else {
        setMsg(out?.error || 'Training failed');
      }
      await load();
    } catch (err: any) {
      setMsg(err?.message || 'Training failed');
    } finally {
      setBusy(false);
    }
  }

  async function promote() {
    if (!model?.symbol) return;
    setBusy(true);
    setMsg('');
    try {
      const out = await promoteModelToPaper(model.symbol, model.path || model.artifact_path || '', confirm || '');
      if (out?.ok) {
        setMsg('Model promoted to paper inference successfully.');
        setConfirm('');
      } else {
        setMsg(out?.error || 'Promotion failed');
      }
      await load();
    } catch (err: any) {
      setMsg(err?.message || 'Promotion failed');
    } finally {
      setBusy(false);
    }
  }

  return (
    <section>
      <PageHeader title="Model Lab" subtitle="Train baseline models, compare test strategies, inspect top wallets, and manage paper promotion safely." />
      <div className="card glass-card">
        <div className="toolbar">
          <label>Symbol</label>
          <select value={symbol} onChange={(e) => setSymbol(e.target.value)}>
            <option value="BTC">BTC</option>
            <option value="ETH">ETH</option>
            <option value="SOL">SOL</option>
          </select>
          <button className="btn" onClick={trainNow} disabled={busy}>{busy ? 'Training…' : 'Train Baseline'}</button>
        </div>
        {msg && <p className="muted">{msg}</p>}
      </div>

      <div className="grid" style={{ gridTemplateColumns: '1fr 1fr', marginTop: 12 }}>
        <div className="card table-wrap glass-card">
          <h3 style={{ marginTop: 0 }}>Test Strategies ({symbol})</h3>
          <table className="responsive-table">
            <thead><tr><th>Name</th><th>Trades</th><th>Win Rate</th><th>PnL Proxy</th></tr></thead>
            <tbody>
              {bench.map((s) => (
                <tr key={s.name}><td data-label="Name">{s.name}</td><td data-label="Trades">{s.trades}</td><td data-label="Win Rate">{Number(s.win_rate || 0).toFixed(1)}%</td><td data-label="PnL Proxy">{Number(s.pnl_proxy || 0).toFixed(6)}</td></tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="card glass-card">
          <h3 style={{ marginTop: 0 }}>Latest Model</h3>
          {model ? (
            <>
              <div className="muted">Type: {model.model_type}</div>
              <div className="muted">Created: {new Date(Number(model.created_at_ms || 0)).toLocaleString()}</div>
              <div className="muted">Accuracy: {(Number(model.metrics?.accuracy || 0) * 100).toFixed(1)}%</div>
              <div className="muted">Precision: {(Number(model.metrics?.precision || 0) * 100).toFixed(1)}%</div>
              <div className="muted">Recall: {(Number(model.metrics?.recall || 0) * 100).toFixed(1)}%</div>
              <div className="toolbar" style={{ marginTop: 8 }}>
                <input value={confirm} onChange={(e) => setConfirm(e.target.value)} placeholder="Type PROMOTE to confirm" />
                <button className="btn" onClick={promote} disabled={busy || !model}>Promote to Paper Inference</button>
              </div>
              <div className="muted">Active paper model: {activePaper?.model_path || 'none'}</div>
            </>
          ) : <div className="muted">No model artifact yet.</div>}

          <h4 style={{ marginTop: 16 }}>Top Wallets (Cohort)</h4>
          <div className="trace-list">
            {wallets.length === 0 ? <div className="muted">No cohort data yet.</div> : wallets.map((w) => (
              <div key={w.wallet_id} className="muted">#{w.rank} {w.wallet_id} · score {Number(w.score_total || 0).toFixed(3)}</div>
            ))}
          </div>
        </div>
      </div>

      <div className="card table-wrap glass-card" style={{ marginTop: 12 }}>
        <h3 style={{ marginTop: 0 }}>Training Job History</h3>
        <table className="responsive-table">
          <thead><tr><th>Started</th><th>Symbol</th><th>Status</th><th>Artifact</th></tr></thead>
          <tbody>
            {jobs.length === 0 ? <tr><td colSpan={4} className="muted">No jobs yet.</td></tr> : jobs.map((j, idx) => (
              <tr key={`${j.started_at_ms}-${idx}`}>
                <td data-label="Started">{j.started_at_ms ? new Date(Number(j.started_at_ms)).toLocaleString() : 'n/a'}</td>
                <td data-label="Symbol">{j.symbol || 'n/a'}</td>
                <td data-label="Status">{j.ok ? 'ok' : `error: ${j.error || 'unknown'}`}</td>
                <td data-label="Artifact">{j.artifact_path || 'n/a'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="card table-wrap glass-card" style={{ marginTop: 12 }}>
        <h3 style={{ marginTop: 0 }}>Agent Decision Packets ({symbol})</h3>
        <table className="responsive-table">
          <thead><tr><th>Time</th><th>Agent</th><th>Action</th><th>Confidence</th><th>Rationale</th><th>Risk</th><th>Execution</th></tr></thead>
          <tbody>
            {packets.length === 0 ? <tr><td colSpan={7} className="muted">No decision packets yet.</td></tr> : packets.map((p, idx) => (
              <tr key={`${p.id}-${idx}`}>
                <td data-label="Time">{p.ts ? new Date(Number(p.ts)).toLocaleString() : 'n/a'}</td>
                <td data-label="Agent">{p.agent_id}</td>
                <td data-label="Action">{p.action}</td>
                <td data-label="Confidence">{p.confidence == null ? 'n/a' : Number(p.confidence).toFixed(3)}</td>
                <td data-label="Rationale">{p.rationale || 'n/a'}</td>
                <td data-label="Risk">{typeof p.risk_json === 'object' ? JSON.stringify(p.risk_json) : String(p.risk_json || 'n/a')}</td>
                <td data-label="Execution">{typeof p.execution_json === 'object' ? JSON.stringify(p.execution_json) : String(p.execution_json || 'n/a')}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
