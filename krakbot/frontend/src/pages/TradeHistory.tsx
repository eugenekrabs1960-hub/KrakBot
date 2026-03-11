import { useEffect, useState } from 'react';
import PageHeader from '../components/PageHeader';
import Badge from '../components/Badge';
import { getEifFilterDecisions, getEifTradeTrace, listTrades } from '../services/api';

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

  return (
    <section>
      <PageHeader title="Trades & Decision Trace" subtitle="Inspect fills, allow/skip decisions, and reasoning chain in one place." />
      <div className="grid" style={{ gridTemplateColumns: '1.3fr 1fr' }}>
        <div className="card table-wrap">
          <h3>Recent Trades</h3>
          <table><thead><tr><th>Strategy</th><th>Side</th><th>Qty</th><th>Entry</th><th>PnL</th></tr></thead><tbody>
            {trades.map((t, i) => <tr key={`${t.ts}-${i}`}><td>{t.strategy_instance_id}</td><td>{t.side}</td><td>{t.qty}</td><td>{Number(t.entry_price || 0).toFixed(4)}</td><td>{Number(t.realized_pnl_usd || 0).toFixed(2)}</td></tr>)}
          </tbody></table>
        </div>
        <div className="card">
          <h3>Decision Inspector</h3>
          {decisions.slice(0, 8).map((d) => (
            <div key={d.id} style={{ marginBottom: 10 }}>
              <Badge tone={d.allowed ? 'good' : 'bad'}>{d.allowed ? 'ALLOW' : 'SKIP'}</Badge> {d.reason_code}
              <div className="muted">{d.strategy_instance_id} · {d.market}</div>
            </div>
          ))}
          <h4>Trace Context</h4>
          {trace.slice(0, 5).map((t) => <div key={t.id} className="muted">{t.event_type} · {t.strategy_instance_id}</div>)}
        </div>
      </div>
    </section>
  );
}
