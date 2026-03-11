import { useEffect, useMemo, useState } from 'react';
import PageHeader from '../components/PageHeader';
import Badge from '../components/Badge';
import { getEifFilterDecisions, getEifTradeTrace, listTrades } from '../services/api';

function fmtTs(ts: any) {
  const n = Number(ts);
  if (!Number.isFinite(n) || n <= 0) return 'n/a';
  return new Date(n).toLocaleString();
}

export default function TradeHistory() {
  const [trades, setTrades] = useState<any[]>([]);
  const [decisions, setDecisions] = useState<any[]>([]);
  const [trace, setTrace] = useState<any[]>([]);

  useEffect(() => {
    const load = async () => {
      const [t, d, tr] = await Promise.all([
        listTrades(30).catch(() => ({ items: [] })),
        getEifFilterDecisions({ limit: 30 }).catch(() => ({ items: [] })),
        getEifTradeTrace({ limit: 30 }).catch(() => ({ items: [] })),
      ]);
      setTrades(t.items || []);
      setDecisions(d.items || []);
      setTrace(tr.items || []);
    };
    load();
    const timer = setInterval(load, 15000);
    return () => clearInterval(timer);
  }, []);

  const latestDecisionByStrategy = useMemo(() => {
    const map: Record<string, any> = {};
    for (const d of decisions) {
      const key = d.strategy_instance_id || 'unknown';
      if (!map[key]) map[key] = d;
    }
    return map;
  }, [decisions]);

  return (
    <section>
      <PageHeader title="Trades & Decision Trace" subtitle="See what happened, why it happened, and the latest filter context by strategy." />
      <div className="card glass-card compact" style={{ marginBottom: 12 }}>
        <span className="muted">Comparison-first trace: trades are paired with most recent filter decision and trace events for fast post-trade review.</span>
      </div>
      <div className="grid" style={{ gridTemplateColumns: '1.35fr 1fr' }}>
        <div className="card table-wrap glass-card">
          <h3 style={{ marginTop: 0 }}>What happened (Recent Trades)</h3>
          <table className="responsive-table"><thead><tr><th>Time</th><th>Strategy</th><th>Action</th><th>Qty</th><th>Entry</th><th>PnL</th><th>Why now</th></tr></thead><tbody>
            {trades.map((t, i) => {
              const latestDecision = latestDecisionByStrategy[t.strategy_instance_id];
              return (
                <tr key={`${t.ts}-${i}`}>
                  <td data-label="Time">{fmtTs(t.ts)}</td>
                  <td data-label="Strategy">{t.strategy_instance_id}</td>
                  <td data-label="Action">{t.side}</td>
                  <td data-label="Qty">{t.qty}</td>
                  <td data-label="Entry">{Number(t.entry_price || 0).toFixed(4)}</td>
                  <td data-label="PnL">{Number(t.realized_pnl_usd || 0).toFixed(2)}</td>
                  <td data-label="Why now" className="muted">{latestDecision?.reason_code || 'No recent reason code'}</td>
                </tr>
              );
            })}
          </tbody></table>
        </div>

        <div className="card glass-card">
          <h3 style={{ marginTop: 0 }}>Why (Decision Inspector)</h3>
          {decisions.slice(0, 8).map((d) => (
            <div key={d.id} className="decision-item">
              <Badge tone={d.allowed ? 'good' : 'bad'}>{d.allowed ? 'ALLOW' : 'SKIP'}</Badge> {d.reason_code}
              <div className="muted">{d.strategy_instance_id} · {d.market}</div>
            </div>
          ))}

          <h4>Trace Context</h4>
          <div className="trace-list">
            {trace.slice(0, 8).map((t) => <div key={t.id} className="muted">{t.event_type} · {t.strategy_instance_id}</div>)}
          </div>
        </div>
      </div>
    </section>
  );
}
