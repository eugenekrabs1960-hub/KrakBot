import { useEffect, useMemo, useState } from 'react';
import PageHeader from '../components/PageHeader';
import { getActivePaperModel, getAgentDecisionPackets } from '../services/api';

type ArenaModel = {
  id: string;
  label: string;
  status: 'online' | 'idle';
  pnl: number;
  winRate: number;
  trades: number;
  avgConfidence: number;
  longBias: number;
  shortBias: number;
  latestReason: string;
  symbols: string[];
};

function pct(v: number) {
  return `${v.toFixed(1)}%`;
}

function scoreModel(model: ArenaModel) {
  return model.pnl * 0.5 + model.winRate * 0.35 + model.avgConfidence * 15 + model.trades * 0.02;
}

export default function ModelArena() {
  const [packets, setPackets] = useState<any[]>([]);
  const [activePaper, setActivePaper] = useState<any>(null);

  useEffect(() => {
    const load = async () => {
      const [packetRes, activeRes] = await Promise.all([
        getAgentDecisionPackets(300).catch(() => ({ items: [] })),
        getActivePaperModel().catch(() => ({ item: null })),
      ]);
      setPackets(packetRes?.items || []);
      setActivePaper(activeRes?.item || null);
    };
    load();
  }, []);

  const rankedModels = useMemo<ArenaModel[]>(() => {
    const byAgent = new Map<string, any[]>();
    for (const p of packets) {
      const key = String(p.agent_id || 'unassigned');
      if (!byAgent.has(key)) byAgent.set(key, []);
      byAgent.get(key)!.push(p);
    }

    const models: ArenaModel[] = Array.from(byAgent.entries()).map(([agentId, rows]) => {
      let wins = 0;
      let losses = 0;
      let pnl = 0;
      let confidenceTotal = 0;
      let confidenceCount = 0;
      let longCount = 0;
      let shortCount = 0;
      const symbols = new Set<string>();

      for (const row of rows) {
        const action = String(row.action || '').toLowerCase();
        if (action === 'buy' || action === 'long') longCount += 1;
        if (action === 'sell' || action === 'short') shortCount += 1;

        if (row.symbol) symbols.add(String(row.symbol));

        if (typeof row.confidence === 'number') {
          confidenceTotal += row.confidence;
          confidenceCount += 1;
        }

        const outcome = row.outcome_json || {};
        const realized = Number(outcome.realized_pnl_usd ?? outcome.pnl_usd ?? 0);
        if (!Number.isNaN(realized)) pnl += realized;

        if (typeof outcome.win === 'boolean') {
          if (outcome.win) wins += 1;
          else losses += 1;
        } else if (!Number.isNaN(realized) && realized !== 0) {
          if (realized > 0) wins += 1;
          else losses += 1;
        }
      }

      const trades = rows.length;
      const decided = Math.max(1, wins + losses);
      const avgConfidence = confidenceCount > 0 ? confidenceTotal / confidenceCount : 0;
      const latest = rows[0] || {};

      return {
        id: agentId,
        label: agentId,
        status: trades > 0 ? 'online' : 'idle',
        pnl,
        trades,
        winRate: (wins / decided) * 100,
        avgConfidence,
        longBias: trades > 0 ? (longCount / trades) * 100 : 0,
        shortBias: trades > 0 ? (shortCount / trades) * 100 : 0,
        latestReason: latest.rationale || 'No rationale captured yet.',
        symbols: Array.from(symbols),
      };
    });

    return models.sort((a, b) => scoreModel(b) - scoreModel(a));
  }, [packets]);

  const [selected, setSelected] = useState<string[]>([]);

  useEffect(() => {
    if (rankedModels.length === 0) {
      setSelected([]);
      return;
    }
    setSelected((prev) => {
      const filtered = prev.filter((id) => rankedModels.some((m) => m.id === id));
      if (filtered.length >= 2) return filtered.slice(0, 2);
      const add = rankedModels.map((m) => m.id).filter((id) => !filtered.includes(id));
      return [...filtered, ...add].slice(0, 2);
    });
  }, [rankedModels]);

  const selectedModels = rankedModels.filter((m) => selected.includes(m.id)).slice(0, 2);

  const toggleSelection = (id: string) => {
    setSelected((prev) => {
      if (prev.includes(id)) return prev.filter((x) => x !== id);
      if (prev.length >= 2) return [prev[1], id];
      return [...prev, id];
    });
  };

  return (
    <section>
      <PageHeader
        title="Model Arena"
        subtitle="Ranked model cards and side-by-side agent comparison for paper-first execution selection."
      />

      <div className="card glass-card compact" style={{ marginBottom: 12 }}>
        <strong>Active Paper Model:</strong>{' '}
        <span className="muted">{activePaper?.model_path || 'none selected'}</span>
      </div>

      <div className="arena-grid">
        {rankedModels.length === 0 ? (
          <div className="card glass-card">No agent decision packets yet. Start agent traffic to populate Arena rankings.</div>
        ) : (
          rankedModels.map((model, idx) => (
            <article key={model.id} className={`card glass-card arena-card ${selected.includes(model.id) ? 'selected' : ''}`}>
              <div className="arena-card-head">
                <div>
                  <div className="muted">Rank #{idx + 1}</div>
                  <h3>{model.label}</h3>
                </div>
                <span className={`badge ${model.status === 'online' ? 'good' : 'warn'}`}>{model.status}</span>
              </div>
              <div className="arena-stats">
                <div><span className="muted">PnL</span><strong>{model.pnl.toFixed(2)} USD</strong></div>
                <div><span className="muted">Win rate</span><strong>{pct(model.winRate)}</strong></div>
                <div><span className="muted">Trades</span><strong>{model.trades}</strong></div>
                <div><span className="muted">Avg confidence</span><strong>{pct(model.avgConfidence * 100)}</strong></div>
              </div>
              <div className="muted">Symbols: {model.symbols.length > 0 ? model.symbols.join(', ') : 'n/a'}</div>
              <button className={`btn ${selected.includes(model.id) ? 'active' : ''}`} onClick={() => toggleSelection(model.id)}>
                {selected.includes(model.id) ? 'Selected for Compare' : 'Compare'}
              </button>
            </article>
          ))
        )}
      </div>

      <div className="card glass-card" style={{ marginTop: 12 }}>
        <h3 style={{ marginTop: 0 }}>Side-by-side Compare</h3>
        {selectedModels.length === 0 ? (
          <div className="muted">Select one or two models to compare.</div>
        ) : (
          <div className="arena-compare-grid">
            {selectedModels.map((model) => (
              <article key={model.id} className="arena-compare-pane">
                <h4>{model.label}</h4>
                <div className="muted">Win rate: {pct(model.winRate)}</div>
                <div className="muted">PnL: {model.pnl.toFixed(2)} USD</div>
                <div className="muted">Trades: {model.trades}</div>
                <div className="muted">Long/Short bias: {pct(model.longBias)} / {pct(model.shortBias)}</div>
                <div className="muted">Avg confidence: {pct(model.avgConfidence * 100)}</div>
                <div style={{ marginTop: 8 }}>
                  <strong>Latest rationale</strong>
                  <p className="muted" style={{ marginBottom: 0 }}>{model.latestReason}</p>
                </div>
              </article>
            ))}
          </div>
        )}
      </div>
    </section>
  );
}
