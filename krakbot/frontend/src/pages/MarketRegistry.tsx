import { useEffect, useMemo, useState } from 'react';
import PageHeader from '../components/PageHeader';
import Badge from '../components/Badge';

export default function MarketRegistry() {
  const [items, setItems] = useState<any[]>([]);
  const [query, setQuery] = useState('');

  async function load() {
    const res = await fetch('/api/markets');
    const data = await res.json();
    setItems(data.items || []);
  }

  async function toggle(id: string, enabled: boolean) {
    await fetch(`/api/markets/${id}/toggle`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ enabled: !enabled }) });
    await load();
  }

  useEffect(() => { load().catch(() => setItems([])); }, []);

  const filtered = useMemo(() => items.filter((m) => `${m.symbol} ${m.venue}`.toLowerCase().includes(query.toLowerCase())), [items, query]);

  return (
    <section>
      <PageHeader title="Market Registry" subtitle="Enable/disable tradable markets with a safer visibility-first workflow." />
      <div className="toolbar"><input placeholder="Filter market or venue" value={query} onChange={(e) => setQuery(e.target.value)} /></div>
      <div className="card table-wrap" style={{ marginTop: 12 }}>
        <table><thead><tr><th>Symbol</th><th>Venue</th><th>Type</th><th>Status</th><th>Action</th></tr></thead><tbody>
          {filtered.map((m) => (
            <tr key={m.id}>
              <td>{m.symbol}</td><td>{m.venue}</td><td>{m.instrument_type}</td>
              <td><Badge tone={m.enabled ? 'good' : 'warn'}>{m.enabled ? 'enabled' : 'disabled'}</Badge></td>
              <td><button className="btn" onClick={() => toggle(m.id, m.enabled)}>{m.enabled ? 'Disable' : 'Enable'}</button></td>
            </tr>
          ))}
        </tbody></table>
      </div>
    </section>
  );
}
