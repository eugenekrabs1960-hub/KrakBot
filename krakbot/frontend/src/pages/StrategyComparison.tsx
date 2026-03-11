import { FormEvent, useEffect, useMemo, useState } from 'react';
import PageHeader from '../components/PageHeader';
import { createStrategyInstance, getEifScorecards, getStrategySummary, listStrategies } from '../services/api';

function StatusDot({ enabled }: { enabled: boolean }) {
  return <span className={`status-dot ${enabled ? 'good' : 'warn'}`} title={enabled ? 'active' : 'inactive'} />;
}

export default function StrategyComparison() {
  const [rows, setRows] = useState<any[]>([]);
  const [scorecards, setScorecards] = useState<any[]>([]);
  const [summary, setSummary] = useState<any>(null);
  const [form, setForm] = useState({
    strategy_name: 'trend_following',
    market: 'SOL/USD',
    starting_equity_usd: 10000,
    display_name: '',
    description: '',
  });
  const [createMsg, setCreateMsg] = useState('');

  async function load() {
    const [strategies, stratSummary, cards] = await Promise.all([
      listStrategies().catch(() => []),
      getStrategySummary().catch(() => null),
      getEifScorecards({ limit: 150 }).catch(() => ({ items: [] })),
    ]);
    setRows(Array.isArray(strategies) ? strategies : []);
    setSummary(stratSummary?.item || null);
    setScorecards(cards?.items || []);
  }

  useEffect(() => {
    load();
    const t = setInterval(load, 15000);
    return () => clearInterval(t);
  }, []);

  async function onCreate(e: FormEvent) {
    e.preventDefault();
    setCreateMsg('');
    try {
      await createStrategyInstance({
        strategy_name: form.strategy_name as 'trend_following' | 'mean_reversion' | 'breakout',
        market: form.market,
        starting_equity_usd: Number(form.starting_equity_usd),
        params: {
          display_name: form.display_name || undefined,
          description: form.description || undefined,
        },
      });
      setCreateMsg('Strategy added successfully.');
      await load();
    } catch (err: any) {
      setCreateMsg(err?.message || 'Failed to create strategy');
    }
  }

  const scoreByStrategy = useMemo(() => {
    const m: Record<string, number> = {};
    scorecards.forEach((s) => { m[s.strategy_instance_id] = (m[s.strategy_instance_id] || 0) + Number(s.expectancy || 0); });
    return m;
  }, [scorecards]);

  return (
    <section>
      <PageHeader title="Strategy Comparison" subtitle="Compare strategy health quickly, with friendlier names and clear status dots." />
      {summary && <div className="card"><strong>Aggregate PnL:</strong> {Number(summary.aggregate_pnl_usd || 0).toFixed(2)} | <strong>Enabled:</strong> {summary.enabled_strategies}/{summary.total_strategies}</div>}

      <form className="card" style={{ marginTop: 12 }} onSubmit={onCreate}>
        <h3 style={{ marginTop: 0 }}>Add Strategy Manually</h3>
        <div className="toolbar">
          <select value={form.strategy_name} onChange={(e) => setForm({ ...form, strategy_name: e.target.value })}>
            <option value="trend_following">Trend Following</option>
            <option value="mean_reversion">Mean Reversion</option>
            <option value="breakout">Breakout</option>
          </select>
          <input value={form.market} onChange={(e) => setForm({ ...form, market: e.target.value })} placeholder="Market (SOL/USD)" />
          <input type="number" value={form.starting_equity_usd} onChange={(e) => setForm({ ...form, starting_equity_usd: Number(e.target.value) })} placeholder="Starting equity" />
        </div>
        <div className="toolbar" style={{ marginTop: 8 }}>
          <input value={form.display_name} onChange={(e) => setForm({ ...form, display_name: e.target.value })} placeholder="Friendly name (e.g. SOL Swing Hunter)" />
          <input value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} placeholder="Description" style={{ minWidth: 340 }} />
          <button className="btn" type="submit">Add</button>
        </div>
        {createMsg && <p className="muted" style={{ marginBottom: 0 }}>{createMsg}</p>}
      </form>

      <div className="card table-wrap" style={{ marginTop: 12 }}>
        <table>
          <thead><tr><th>Strategy</th><th>Status</th><th>PnL</th><th>Win Rate</th><th>Trades</th><th>Edge Score</th></tr></thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.strategy_instance_id}>
                <td>
                  <strong>{r.display_name || r.name}</strong>
                  <div className="muted">{r.description || 'No description yet.'}</div>
                </td>
                <td><StatusDot enabled={Boolean(r.enabled)} /></td>
                <td>{Number(r.pnl_usd || 0).toFixed(2)}</td>
                <td>{Number(r.win_rate_pct || 0).toFixed(1)}%</td>
                <td>{r.trade_count}</td>
                <td>{Number(scoreByStrategy[r.strategy_instance_id] || 0).toFixed(3)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
