import { useEffect, useState } from 'react';
import PageHeader from '../components/PageHeader';
import Badge from '../components/Badge';
import { getStrategyDetail, listStrategies } from '../services/api';

export default function StrategyDetail() {
  const [strategies, setStrategies] = useState<any[]>([]);
  const [selected, setSelected] = useState<string>('');
  const [detail, setDetail] = useState<any>(null);

  useEffect(() => {
    listStrategies().then((rows) => {
      const items = Array.isArray(rows) ? rows : [];
      setStrategies(items);
      if (items[0]?.strategy_instance_id) setSelected(items[0].strategy_instance_id);
    }).catch(() => setStrategies([]));
  }, []);

  useEffect(() => {
    if (!selected) return;
    getStrategyDetail(selected).then((d) => setDetail(d.item || null)).catch(() => setDetail(null));
  }, [selected]);

  return (
    <section>
      <PageHeader title="Strategy Detail" subtitle="Deep dive into a single strategy instance." />
      <div className="card glass-card compact">
        <div className="toolbar">
          <label>Strategy</label>
          <select value={selected} onChange={(e) => setSelected(e.target.value)}>
            {strategies.map((s) => <option key={s.strategy_instance_id} value={s.strategy_instance_id}>{s.name} ({s.strategy_instance_id})</option>)}
          </select>
        </div>
      </div>

      <div className="grid" style={{ gridTemplateColumns: '1fr 1fr', marginTop: 12 }}>
        <div className="card glass-card">
          {!detail ? <p className="muted">No strategy detail loaded.</p> : (
            <>
              <h3 style={{ marginTop: 0 }}>Strategy Identity</h3>
              <p><strong>ID:</strong> {detail.strategy_instance_id}</p>
              <p><strong>Status:</strong> <Badge tone={detail.enabled ? 'good' : 'warn'}>{detail.status || 'unknown'}</Badge></p>
              <p><strong>Market:</strong> {detail.market}</p>
            </>
          )}
        </div>
        <div className="card glass-card">
          {!detail ? <p className="muted">Awaiting strategy payload.</p> : (
            <>
              <h3 style={{ marginTop: 0 }}>Position & PnL</h3>
              <p><strong>Position:</strong> {Number(detail.current_position_qty || 0).toFixed(4)}</p>
              <p><strong>Avg Entry:</strong> {Number(detail.avg_entry_price || 0).toFixed(4)}</p>
              <p><strong>Realized PnL:</strong> {Number(detail.realized_pnl_usd || 0).toFixed(2)}</p>
            </>
          )}
        </div>
      </div>
    </section>
  );
}
