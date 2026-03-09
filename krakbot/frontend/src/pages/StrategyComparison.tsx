import { useEffect, useState } from 'react';

type StrategyRow = {
  strategy_instance_id: string;
  name: string;
  enabled: boolean;
  status: string;
  market: string;
  pnl_usd: number;
  drawdown_pct: number;
  win_rate_pct: number;
  trade_count: number;
  current_position_qty: number;
  equity_usd: number;
};

export default function StrategyComparison() {
  const [rows, setRows] = useState<StrategyRow[]>([]);

  useEffect(() => {
    fetch('/api/strategies')
      .then((r) => r.json())
      .then(setRows)
      .catch(() => setRows([]));
  }, []);

  return (
    <section>
      <h2>Strategy Comparison</h2>
      {rows.length === 0 ? (
        <p>No strategy instances yet.</p>
      ) : (
        <ul>
          {rows.map((r) => (
            <li key={r.strategy_instance_id}>
              {r.name} | enabled: {String(r.enabled)} | status: {r.status} | pnl: {r.pnl_usd.toFixed(2)} | dd: {r.drawdown_pct.toFixed(2)}% | win: {r.win_rate_pct.toFixed(1)}% | trades: {r.trade_count} | pos: {r.current_position_qty} | equity: {r.equity_usd.toFixed(2)}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
