import { useEffect, useMemo, useState } from 'react';
import PageHeader from '../components/PageHeader';
import {
  getActiveExecutionModel,
  getAgentDecisionPackets,
  getJasonTrades,
  getJasonState,
  setActiveExecutionModel,
} from '../services/api';

type ArenaModel = {
  id: string;
  label: string;
  status: 'online' | 'idle';
  pnl: number;
  winRate: number;
  trades: number;
  decisions: number;
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

function prettyJson(value: unknown) {
  try {
    return JSON.stringify(value ?? {}, null, 2);
  } catch {
    return String(value ?? '');
  }
}

export default function ModelArena() {
  const [packets, setPackets] = useState<any[]>([]);
  const [activeExecution, setActiveExecution] = useState<any>(null);
  const [jasonTrades, setJasonTrades] = useState<any[]>([]);
  const [jasonState, setJasonState] = useState<any>(null);

  const [selected, setSelected] = useState<string[]>([]);
  const [switchCandidate, setSwitchCandidate] = useState<string | null>(null);
  const [switchConfirm, setSwitchConfirm] = useState('');
  const [switchMsg, setSwitchMsg] = useState('');
  const [switchBusy, setSwitchBusy] = useState(false);

  const [symbolFilter, setSymbolFilter] = useState('all');
  const [agentFilter, setAgentFilter] = useState('all');
  const [timeFilter, setTimeFilter] = useState<'1h' | '6h' | '24h' | 'all'>('6h');
  const [focusedPacketId, setFocusedPacketId] = useState<number | null>(null);
  const [showInspector, setShowInspector] = useState(false);
  const [expandedModelId, setExpandedModelId] = useState<string | null>(null);

  const load = async () => {
    const [packetRes, execRes, jsTrades, jsState] = await Promise.all([
      getAgentDecisionPackets(500).catch(() => ({ items: [] })),
      getActiveExecutionModel().catch(() => ({ item: null })),
      getJasonTrades(30).catch(() => ({ items: [] })),
      getJasonState().catch(() => ({ ok: false })),
    ]);
    setPackets(packetRes?.items || []);
    setActiveExecution(execRes?.item || null);
    setJasonTrades(jsTrades?.items || []);
    setJasonState(jsState || null);
  };

  useEffect(() => {
    load();
  }, []);

  const timeCutoff = useMemo(() => {
    if (timeFilter === 'all') return 0;
    const now = Date.now();
    if (timeFilter === '1h') return now - 60 * 60 * 1000;
    if (timeFilter === '6h') return now - 6 * 60 * 60 * 1000;
    return now - 24 * 60 * 60 * 1000;
  }, [timeFilter]);

  const filteredPackets = useMemo(() => {
    return packets.filter((p) => {
      const ts = Number(p.ts || 0);
      if (timeCutoff > 0 && ts < timeCutoff) return false;
      if (symbolFilter !== 'all' && String(p.symbol || '').toUpperCase() !== symbolFilter) return false;
      if (agentFilter !== 'all' && String(p.agent_id || '') !== agentFilter) return false;
      return true;
    });
  }, [packets, timeCutoff, symbolFilter, agentFilter]);

  const uniqueSymbols = useMemo(() => {
    return Array.from(new Set(packets.map((p) => String(p.symbol || '').toUpperCase()).filter(Boolean))).sort();
  }, [packets]);

  const uniqueAgents = useMemo(() => {
    return Array.from(new Set(packets.map((p) => String(p.agent_id || '')).filter(Boolean))).sort();
  }, [packets]);

  const rankedModels = useMemo<ArenaModel[]>(() => {
    const byAgent = new Map<string, any[]>();
    for (const p of filteredPackets) {
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
        if (action === 'close' || action === 'exit') shortCount += 0;

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

      const decisions = rows.length;
      const trades = rows.filter((r) => {
        const a = String(r.action || '').toLowerCase();
        return ['long', 'short', 'buy', 'sell', 'close', 'exit'].includes(a);
      }).length;
      const decided = Math.max(1, wins + losses);
      const avgConfidence = confidenceCount > 0 ? confidenceTotal / confidenceCount : 0;
      const latest = rows[0] || {};

      const label = agentId === 'jason' ? 'GPT 5.4' : agentId;
      return {
        id: agentId,
        label,
        status: decisions > 0 ? 'online' : 'idle',
        pnl,
        trades,
        decisions,
        winRate: (wins / decided) * 100,
        avgConfidence,
        longBias: trades > 0 ? (longCount / trades) * 100 : 0,
        shortBias: trades > 0 ? (shortCount / trades) * 100 : 0,
        latestReason: latest.rationale || 'No rationale captured yet.',
        symbols: Array.from(symbols),
      };
    });

    return models.sort((a, b) => scoreModel(b) - scoreModel(a));
  }, [filteredPackets]);

  useEffect(() => {
    if (rankedModels.length === 0) {
      setSelected([]);
      setExpandedModelId(null);
      return;
    }
    setSelected((prev) => {
      const filtered = prev.filter((id) => rankedModels.some((m) => m.id === id));
      if (filtered.length >= 2) return filtered.slice(0, 2);
      const add = rankedModels.map((m) => m.id).filter((id) => !filtered.includes(id));
      return [...filtered, ...add].slice(0, 2);
    });
    setExpandedModelId((prev) => prev && rankedModels.some((m) => m.id === prev) ? prev : rankedModels[0].id);
  }, [rankedModels]);

  const selectedModels = rankedModels.filter((m) => selected.includes(m.id)).slice(0, 2);
  const comparisonAgentSet = useMemo(() => new Set(selectedModels.map((m) => m.id)), [selectedModels]);

  const timelinePackets = useMemo(() => {
    const source = comparisonAgentSet.size > 0
      ? filteredPackets.filter((p) => comparisonAgentSet.has(String(p.agent_id || '')))
      : filteredPackets;
    return source.slice(0, 80);
  }, [filteredPackets, comparisonAgentSet]);

  const focusedPacket = useMemo(() => {
    if (focusedPacketId == null) return timelinePackets[0] || null;
    return timelinePackets.find((p) => Number(p.id) === focusedPacketId) || timelinePackets[0] || null;
  }, [timelinePackets, focusedPacketId]);

  const expandedModel = useMemo(
    () => rankedModels.find((m) => m.id === expandedModelId) || rankedModels[0] || null,
    [rankedModels, expandedModelId],
  );

  const expandedModelPackets = useMemo(() => {
    if (!expandedModel) return [] as any[];
    return filteredPackets.filter((p) => String(p.agent_id || '') === expandedModel.id).slice(0, 40);
  }, [filteredPackets, expandedModel]);

  const expandedTradeRows = useMemo(() => {
    if (!expandedModel) return [] as any[];
    if (expandedModel.id === 'jason' && jasonTrades.length > 0) {
      return jasonTrades.slice(0, 20).map((t) => ({
        key: `jt-${t.id}`,
        ts: t.opened_at_ms,
        action: t.side,
        symbol: t.symbol,
        leverage: `${Number(t.leverage || 0).toFixed(1)}x`,
        entry: Number(t.entry_price || 0).toFixed(2),
        pnl: t.realized_pnl_usd == null
          ? (t.unrealized_pnl_usd == null ? 'n/a' : `${Number(t.unrealized_pnl_usd).toFixed(2)} (uPnL)`)
          : Number(t.realized_pnl_usd).toFixed(2),
        verified: true,
      }));
    }

    return expandedModelPackets
      .filter((p) => ['long', 'short', 'buy', 'sell', 'close', 'exit'].includes(String(p.action || '').toLowerCase()))
      .slice(0, 20)
      .map((p) => ({
        key: `dp-${p.id}`,
        ts: p.ts,
        action: String(p.action || '').toUpperCase(),
        symbol: p.symbol,
        leverage: p.execution_json?.leverage ? `${p.execution_json.leverage}x` : 'n/a',
        entry: p.execution_json?.entry_price ? Number(p.execution_json.entry_price).toFixed(2) : 'n/a',
        pnl: p.outcome_json?.realized_pnl_usd != null ? Number(p.outcome_json.realized_pnl_usd).toFixed(2) : 'n/a',
        verified: false,
      }));
  }, [expandedModel, expandedModelPackets, jasonTrades]);

  const expandedLatestPacket = useMemo(() => expandedModelPackets[0] || null, [expandedModelPackets]);

  const expandedStrategySummary = useMemo(() => {
    if (!expandedModelPackets.length) return 'No strategy narrative yet.';
    const recent = expandedModelPackets.slice(0, 12);
    const holds = recent.filter((p) => String(p.action || '').toLowerCase() === 'hold').length;
    const longShort = recent.filter((p) => ['long', 'short', 'buy', 'sell'].includes(String(p.action || '').toLowerCase())).length;
    const closeCount = recent.filter((p) => ['close', 'exit'].includes(String(p.action || '').toLowerCase())).length;
    const topSymbols = Array.from(new Set(recent.map((p) => String(p.symbol || '').toUpperCase()).filter(Boolean))).slice(0, 3);
    return `${expandedModel.label} recently logged ${recent.length} decisions (${holds} hold, ${longShort} directional, ${closeCount} close). Focus symbols: ${topSymbols.join(', ') || 'n/a'}.`; 
  }, [expandedModelPackets, expandedModel]);

  const expandedPositionReasoning = useMemo(() => {
    if (!expandedLatestPacket) return 'No current position reasoning available.';
    const action = String(expandedLatestPacket.action || '').toLowerCase();
    const rationale = expandedLatestPacket.rationale || 'No rationale provided.';
    if (action === 'hold') return `Holding posture: ${rationale}`;
    if (['close', 'exit'].includes(action)) return `Flat/exit posture: ${rationale}`;
    return `Active ${String(expandedLatestPacket.action || '').toUpperCase()} posture: ${rationale}`;
  }, [expandedLatestPacket]);

  const toggleSelection = (id: string) => {
    setSelected((prev) => {
      if (prev.includes(id)) return prev.filter((x) => x !== id);
      if (prev.length >= 2) return [prev[1], id];
      return [...prev, id];
    });
  };

  const switchExecutionModel = async () => {
    if (!switchCandidate) return;
    setSwitchBusy(true);
    setSwitchMsg('');
    try {
      const out = await setActiveExecutionModel(switchCandidate, switchConfirm || '');
      if (out?.ok) {
        setActiveExecution(out.item || null);
        setSwitchMsg(`Active execution model switched to ${switchCandidate}.`);
        setSwitchCandidate(null);
        setSwitchConfirm('');
      } else {
        setSwitchMsg(out?.error || 'Switch failed');
      }
    } catch (err: any) {
      setSwitchMsg(err?.message || 'Switch failed');
    } finally {
      setSwitchBusy(false);
    }
  };

  return (
    <section>
      <PageHeader
        title="Model Arena"
        subtitle="Clean operator view: who is active, what changed recently, and why each trade happened."
      />

      <div className="card glass-card" style={{ marginBottom: 12 }}>
        <h3 style={{ marginTop: 0 }}>Recent trade actions</h3>
        <div className="trace-list">
          {timelinePackets
            .filter((p) => ['long', 'short', 'buy', 'sell', 'close', 'exit'].includes(String(p.action || '').toLowerCase()))
            .slice(0, 10)
            .map((p) => (
              <div key={`digest-${p.id}`} className="arena-event-row">
                <div>
                  <strong>{String(p.agent_id || 'unknown') === 'jason' ? 'GPT 5.4' : String(p.agent_id || 'unknown')}</strong> {String(p.action || 'n/a').toUpperCase()} {String(p.symbol || 'n/a')}
                  <div className="muted">{p.rationale || 'No rationale provided.'}</div>
                </div>
                <div className="muted">{p.ts ? new Date(Number(p.ts)).toLocaleTimeString() : 'n/a'}</div>
              </div>
            ))}
        </div>
      </div>

      <div className="card glass-card" style={{ marginBottom: 12 }}>
        <div className="toolbar">
          <button className="btn" onClick={load}>Refresh Arena Data</button>
          <button className="btn" onClick={() => { setSymbolFilter('all'); setAgentFilter('all'); setTimeFilter('6h'); }}>Reset View</button>
          <label>Symbol</label>
          <select value={symbolFilter} onChange={(e) => setSymbolFilter(e.target.value)}>
            <option value="all">All</option>
            {uniqueSymbols.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>

          <label>Agent</label>
          <select value={agentFilter} onChange={(e) => setAgentFilter(e.target.value)}>
            <option value="all">All</option>
            {uniqueAgents.map((a) => <option key={a} value={a}>{a}</option>)}
          </select>

          <label>Window</label>
          <select value={timeFilter} onChange={(e) => setTimeFilter(e.target.value as any)}>
            <option value="1h">Last 1h</option>
            <option value="6h">Last 6h</option>
            <option value="24h">Last 24h</option>
            <option value="all">All</option>
          </select>
        </div>
      </div>

      <div className="card glass-card" style={{ marginBottom: 12 }}>
        <h3 style={{ marginTop: 0 }}>Battle Board</h3>
        <div className="muted" style={{ marginBottom: 10 }}>Click a model row to open its reasoning and trade log.</div>
        <div className="arena-board">
          {rankedModels.length === 0 ? (
            <div className="muted">No decision packets in this filter scope.</div>
          ) : rankedModels.map((model, idx) => (
            <button key={model.id} className={`arena-board-row ${expandedModel?.id === model.id ? 'active' : ''}`} onClick={() => setExpandedModelId(model.id)}>
              <div>
                <strong>#{idx + 1} {model.label}</strong>
                <div className="muted">{model.symbols.join(', ') || 'n/a'} · {model.trades} trades / {model.decisions} decisions</div>
              </div>
              <div className="arena-board-pnl">{model.pnl.toFixed(2)} USD</div>
            </button>
          ))}
        </div>
      </div>

      {expandedModel && (
        <div className="card glass-card" style={{ marginBottom: 12 }}>
          <div className="arena-card-head">
            <div>
              <h3 style={{ marginTop: 0 }}>{expandedModel.label}</h3>
              <div className="muted">{expandedModel.id === 'jason' ? ((jasonState?.state?.online === false) ? 'offline' : 'online') : expandedModel.status} · Win {pct(expandedModel.winRate)} · Confidence {pct(expandedModel.avgConfidence * 100)}</div>
              {expandedModel.id === 'jason' && jasonState?.state?.online === false ? (<div className="muted">Offline reason: {String(jasonState?.state?.offline_reason || 'oauth_unavailable')}</div>) : null}
            </div>
            <div className="toolbar">
              <button className={`btn ${selected.includes(expandedModel.id) ? 'active' : ''}`} onClick={() => toggleSelection(expandedModel.id)}>
                {selected.includes(expandedModel.id) ? 'Selected' : 'Compare'}
              </button>
              <button
                className={`btn ${activeExecution?.agent_id === expandedModel.id ? 'active' : ''}`}
                onClick={() => {
                  if (activeExecution?.agent_id === expandedModel.id) return;
                  setSwitchMsg('');
                  setSwitchCandidate(expandedModel.id);
                }}
                disabled={activeExecution?.agent_id === expandedModel.id}
              >
                {activeExecution?.agent_id === expandedModel.id ? 'Active' : 'Set Active'}
              </button>
            </div>
          </div>

          <div className="card compact" style={{ marginBottom: 10 }}>
            <strong>Strategy</strong>
            <p className="muted" style={{ marginBottom: 0 }}>{expandedStrategySummary}</p>
          </div>

          <div className="card compact" style={{ marginBottom: 10 }}>
            <strong>Current Position Reasoning</strong>
            <p className="muted" style={{ marginBottom: 0 }}>{expandedPositionReasoning}</p>
          </div>

          <div className="card table-wrap compact">
            <strong>Trade history</strong>
            <div className="muted" style={{ marginTop: 4 }}>
              {expandedModel.id === 'jason'
                ? 'Verified ledger rows (PnL reflects closed trades only).'
                : 'Inferred from decision packets (PnL/leverage may be partial if model has no execution ledger).'}
            </div>
            <table className="responsive-table" style={{ marginTop: 8 }}>
              <thead><tr><th>Time</th><th>Action</th><th>Symbol</th><th>Lev</th><th>Entry</th><th>PnL</th><th>Source</th></tr></thead>
              <tbody>
                {expandedTradeRows.length === 0 ? <tr><td colSpan={7} className="muted">No executed trades logged yet.</td></tr> : expandedTradeRows.map((r) => (
                  <tr key={r.key}>
                    <td data-label="Time">{r.ts ? new Date(Number(r.ts)).toLocaleString() : 'n/a'}</td>
                    <td data-label="Action">{String(r.action || '').toUpperCase()}</td>
                    <td data-label="Symbol">{r.symbol || 'n/a'}</td>
                    <td data-label="Lev">{r.leverage}</td>
                    <td data-label="Entry">{r.entry}</td>
                    <td data-label="PnL">{r.pnl}</td>
                    <td data-label="Source">{r.verified ? 'ledger' : 'inferred'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {switchCandidate ? (
        <div className="card glass-card" style={{ marginTop: 12 }}>
          <h3 style={{ marginTop: 0 }}>Confirm Execution Model Switch</h3>
          <div className="muted">Switch active execution to <strong>{switchCandidate}</strong>. Type <strong>SWITCH</strong> to confirm.</div>
          <div className="toolbar" style={{ marginTop: 8 }}>
            <input value={switchConfirm} onChange={(e) => setSwitchConfirm(e.target.value)} placeholder="Type SWITCH" />
            <button className="btn" onClick={switchExecutionModel} disabled={switchBusy}>{switchBusy ? 'Switching…' : 'Confirm'}</button>
            <button className="btn" onClick={() => { setSwitchCandidate(null); setSwitchConfirm(''); }}>Cancel</button>
          </div>
          {switchMsg ? <div className="muted" style={{ marginTop: 8 }}>{switchMsg}</div> : null}
        </div>
      ) : switchMsg ? (
        <div className="card glass-card compact" style={{ marginTop: 12 }}>
          <div className="muted">{switchMsg}</div>
        </div>
      ) : null}

      <div className="card glass-card" style={{ marginTop: 12 }}>
        <h3 style={{ marginTop: 0 }}>Compare selected models</h3>
        {selectedModels.length === 0 ? (
          <div className="muted">Select one or two models to compare.</div>
        ) : (
          <div className="arena-compare-grid">
            {selectedModels.map((model) => (
              <article key={model.id} className="arena-compare-pane">
                <h4>{model.label}</h4>
                <div className="muted">Win rate: {pct(model.winRate)}</div>
                <div className="muted">PnL: {model.pnl.toFixed(2)} USD</div>
                <div className="muted">Trades: {model.trades} (Decisions: {model.decisions})</div>
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

      <div className="card glass-card compact" style={{ marginTop: 12 }}>
        <div className="toolbar" style={{ justifyContent: 'space-between' }}>
          <strong>Decision Packet Inspector</strong>
          <button className="btn" onClick={() => setShowInspector((v) => !v)}>{showInspector ? 'Hide Inspector' : 'Show Inspector'}</button>
        </div>
        <div className="muted">Keep this collapsed for cleaner day-to-day monitoring. Open it when you need deep packet forensics.</div>
      </div>

      {showInspector && <div className="card glass-card" style={{ marginTop: 12 }}>
        <h3 style={{ marginTop: 0 }}>Decision Packet Inspector</h3>
        <div className="arena-timeline-wrap">
          <div className="arena-timeline-list">
            {timelinePackets.length === 0 ? (
              <div className="muted">No packets in timeline scope.</div>
            ) : timelinePackets.map((p) => {
              const isActive = Number(p.id) === Number(focusedPacket?.id);
              return (
                <button
                  key={`${p.id}-${p.ts}`}
                  className={`arena-timeline-item ${isActive ? 'active' : ''}`}
                  onClick={() => setFocusedPacketId(Number(p.id))}
                >
                  <div>
                    <strong>{String(p.agent_id || 'unknown')}</strong>
                    <div className="muted">{String(p.symbol || 'n/a')} · {String(p.action || 'n/a').toUpperCase()}</div>
                  </div>
                  <div className="muted">{p.ts ? new Date(Number(p.ts)).toLocaleString() : 'n/a'}</div>
                </button>
              );
            })}
          </div>

          <div className="arena-packet-detail">
            {!focusedPacket ? (
              <div className="muted">Pick a packet to inspect details.</div>
            ) : (
              <>
                <h4 style={{ marginTop: 0 }}>Packet #{focusedPacket.id}</h4>
                <div className="muted" style={{ marginBottom: 8 }}>
                  {focusedPacket.ts ? new Date(Number(focusedPacket.ts)).toLocaleString() : 'n/a'} · {String(focusedPacket.agent_id || 'unknown')} · {String(focusedPacket.symbol || 'n/a')} · {String(focusedPacket.action || 'n/a').toUpperCase()}
                </div>
                <div className="grid" style={{ gridTemplateColumns: '1fr 1fr 1fr', gap: 8 }}>
                  <div className="card compact">
                    <strong>Reason</strong>
                    <p className="muted" style={{ marginBottom: 0 }}>{focusedPacket.rationale || 'No rationale provided.'}</p>
                  </div>
                  <div className="card compact">
                    <strong>Risk</strong>
                    <pre className="arena-json">{prettyJson(focusedPacket.risk_json)}</pre>
                  </div>
                  <div className="card compact">
                    <strong>Execution</strong>
                    <pre className="arena-json">{prettyJson(focusedPacket.execution_json)}</pre>
                  </div>
                </div>
              </>
            )}
          </div>
        </div>
      </div>}
    </section>
  );
}
