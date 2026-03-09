import { useEffect, useState } from 'react';

type MarketRow = {
  id: string;
  venue: string;
  symbol: string;
  base_asset: string;
  quote_asset: string;
  instrument_type: string;
  enabled: boolean;
};

export default function MarketRegistry() {
  const [items, setItems] = useState<MarketRow[]>([]);

  async function load() {
    const res = await fetch('/api/markets');
    const data = await res.json();
    setItems(data.items || []);
  }

  async function toggle(id: string, enabled: boolean) {
    await fetch(`/api/markets/${id}/toggle`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ enabled: !enabled }),
    });
    await load();
  }

  useEffect(() => {
    load().catch(() => setItems([]));
  }, []);

  return (
    <section>
      <h2>Market Registry</h2>
      <ul>
        {items.map((m) => (
          <li key={m.id}>
            {m.symbol} ({m.instrument_type}) [{m.enabled ? 'enabled' : 'disabled'}]{' '}
            <button onClick={() => toggle(m.id, m.enabled)}>
              {m.enabled ? 'disable' : 'enable'}
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}
