import { useEffect, useState } from 'react';
import PageHeader from '../components/PageHeader';
import { getLatestModel, getStrategyBenchmarks, getWalletCohortLatest, trainBaselineModel } from '../services/api';

export default function ModelLab() {
  const [symbol, setSymbol] = useState('BTC');
  const [bench, setBench] = useState<any[]>([]);
  const [model, setModel] = useState<any>(null);
  const [wallets, setWallets] = useState<any[]>([]);
  const [msg, setMsg] = useState('');
  const [busy, setBusy] = useState(false);

  const load = async () => {
    const [b, m, w] = await Promise.all([
      getStrategyBenchmarks(symbol, 50000).catch(() => ({ items: [] })),
      getLatestModel(symbol).catch(() => null),
      getWalletCohortLatest('top_sol_active_wallets').catch(() => ({ members: [] })),
    ]);
    setBench(b?.items || []);
    setModel(m?.item || null);
    setWallets((w?.members || []).slice(0, 10));
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

  return (
    <section>
      <PageHeader title="Model Lab" subtitle="Train baseline models, compare test strategies, and watch top wallet cohorts." />
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
    </section>
  );
}
