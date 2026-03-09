import { useEffect, useState } from 'react';

type MarketSnap = {
  market: string;
  last_price: number | null;
  ts: number | null;
};

export default function MarketData() {
  const [snap, setSnap] = useState<MarketSnap | null>(null);
  const [lastEvent, setLastEvent] = useState<string>('none');

  useEffect(() => {
    fetch('/api/market/snapshot')
      .then((r) => r.json())
      .then(setSnap)
      .catch(() => null);

    const protocol = location.protocol === 'https:' ? 'wss' : 'ws';
    const ws = new WebSocket(`${protocol}://${location.host}/api/ws`);
    ws.onmessage = (ev) => {
      try {
        const msg = JSON.parse(ev.data);
        setLastEvent(msg.type || 'event');
      } catch {
        setLastEvent('parse_error');
      }
    };

    const ping = setInterval(() => {
      if (ws.readyState === ws.OPEN) ws.send('ping');
    }, 10000);

    return () => {
      clearInterval(ping);
      ws.close();
    };
  }, []);

  return (
    <section>
      <h2>Market Data</h2>
      <p>
        {snap?.market ?? 'SOL/USD'} last price: {snap?.last_price ?? 'N/A'}
      </p>
      <p>Last stream event: {lastEvent}</p>
    </section>
  );
}
