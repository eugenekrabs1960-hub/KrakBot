import { useEffect, useState } from 'react';
import PageHeader from '../components/PageHeader';
import StatCard from '../components/StatCard';

function fmtTs(ts: any) {
  const n = Number(ts);
  if (!Number.isFinite(n) || n <= 0) return 'n/a';
  return new Date(n).toLocaleString();
}

export default function MarketData() {
  const [snap, setSnap] = useState<any>(null);
  const [event, setEvent] = useState('none');
  const [trades, setTrades] = useState<any[]>([]);

  useEffect(() => {
    const load = () => {
      fetch('/api/market/snapshot').then((r) => r.json()).then(setSnap).catch(() => setSnap(null));
      fetch('/api/market/trades?limit=50').then((r) => r.json()).then((d) => setTrades(d?.items || [])).catch(() => setTrades([]));
    };
    load();

    const protocol = location.protocol === 'https:' ? 'wss' : 'ws';
    const ws = new WebSocket(`${protocol}://${location.host}/api/ws`);
    ws.onmessage = (ev) => {
      try {
        const msg = JSON.parse(ev.data);
        setEvent(msg.type || 'event');
        if (msg.type === 'trade') load();
      } catch {
        setEvent('parse_error');
      }
    };
    return () => ws.close();
  }, []);

  return (
    <section>
      <PageHeader title="Market Detail" subtitle="Realtime price feed, stream health, and timestamped market trade logs." />
      <div className="grid kpi">
        <StatCard label="Market" value={snap?.market || 'SOL/USD'} />
        <StatCard label="Last Price" value={snap?.last_price ?? 'n/a'} />
        <StatCard label="Snapshot TS" value={fmtTs(snap?.ts)} />
        <StatCard label="Last Stream Event" value={event} />
      </div>

      <div className="card table-wrap glass-card" style={{ marginTop: 12 }}>
        <h3 style={{ marginTop: 0 }}>Market Trade Log</h3>
        <table className="responsive-table">
          <thead><tr><th>Time</th><th>Market</th><th>Side</th><th>Price</th><th>Qty</th></tr></thead>
          <tbody>
            {trades.map((t, i) => (
              <tr key={`${t.event_ts}-${i}`}>
                <td data-label="Time">{fmtTs(t.event_ts)}</td>
                <td data-label="Market">{t.market}</td>
                <td data-label="Side">{t.side}</td>
                <td data-label="Price">{Number(t.price || 0).toFixed(6)}</td>
                <td data-label="Qty">{Number(t.qty || 0).toFixed(6)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
