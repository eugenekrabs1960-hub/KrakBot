import { useEffect, useState } from 'react';
import PageHeader from '../components/PageHeader';
import StatCard from '../components/StatCard';

export default function MarketData() {
  const [snap, setSnap] = useState<any>(null);
  const [event, setEvent] = useState('none');

  useEffect(() => {
    fetch('/api/market/snapshot').then((r) => r.json()).then(setSnap).catch(() => setSnap(null));
    const protocol = location.protocol === 'https:' ? 'wss' : 'ws';
    const ws = new WebSocket(`${protocol}://${location.host}/api/ws`);
    ws.onmessage = (ev) => {
      try { setEvent(JSON.parse(ev.data).type || 'event'); } catch { setEvent('parse_error'); }
    };
    return () => ws.close();
  }, []);

  return (
    <section>
      <PageHeader title="Market Detail" subtitle="Realtime price feed, stream health, and market registry controls." />
      <div className="grid kpi">
        <StatCard label="Market" value={snap?.market || 'SOL/USD'} />
        <StatCard label="Last Price" value={snap?.last_price ?? 'n/a'} />
        <StatCard label="Snapshot TS" value={snap?.ts || 'n/a'} />
        <StatCard label="Last Stream Event" value={event} />
      </div>
    </section>
  );
}
