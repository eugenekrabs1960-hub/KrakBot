import { useEffect, useMemo, useState } from 'react';
import PageHeader from '../components/PageHeader';
import Badge from '../components/Badge';
import { getEifScorecards, getStrategySummary, listStrategies } from '../services/api';

export default function StrategyComparison() {
  const [rows, setRows] = useState<any[]>([]);
  const [scorecards, setScorecards] = useState<any[]>([]);
  const [summary, setSummary] = useState<any>(null);

  useEffect(() => {
    const load = async () => {
      const [strategies, stratSummary, cards] = await Promise.all([
        listStrategies().catch(() => []),
        getStrategySummary().catch(() => null),
        getEifScorecards({ limit: 150 }).catch(() => ({ items: [] })),
      ]);
      setRows(Array.isArray(strategies) ? strategies : []);
      setSummary(stratSummary?.item || null);
      setScorecards(cards?.items || []);
    };
    load();
    const t = setInterval(load, 15000);
    return () => clearInterval(t);
  }, []);

  const scoreByStrategy = useMemo(() => {
    const m: Record<string, number> = {};
    scorecards.forEach((s) => { m[s.strategy_instance_id] = (m[s.strategy_instance_id] || 0) + Number(s.expectancy || 0); });
    return m;
  }, [scorecards]);

  return (
    <section>
      <PageHeader title="Strategy Comparison" subtitle="Compare live strategy health, execution quality, and expected edge." />
      {summary && <div className="card"><strong>Aggregate PnL:</strong> {Number(summary.aggregate_pnl_usd || 0).toFixed(2)} | <strong>Enabled:</strong> {summary.enabled_strategies}/{summary.total_strategies}</div>}
      <div className="card table-wrap" style={{ marginTop: 12 }}>
        <table>
          <thead><tr><th>Strategy</th><th>Status</th><th>PnL</th><th>Win Rate</th><th>Trades</th><th>Edge Score</th></tr></thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.strategy_instance_id}>
                <td>{r.name}<div className="muted">{r.strategy_instance_id}</div></td>
                <td><Badge tone={r.enabled ? 'good' : 'warn'}>{r.status}</Badge></td>
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
