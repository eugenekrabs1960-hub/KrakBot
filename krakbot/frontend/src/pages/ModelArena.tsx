import { useEffect, useMemo, useState } from 'react';
import PageHeader from '../components/PageHeader';
import {
  getActiveExecutionModel,
  getActivePaperModel,
  getAgentDecisionPackets,
  getJasonState,
  getJasonTrades,
  setActiveExecutionModel,
} from '../services/api';

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

function prettyJson(value: unknown) {
  try {
    return JSON.stringify(value ?? {}, null, 2);
  } catch {
    return String(value ?? '');
  }
}

export default function ModelArena() {
  const [packets, setPackets] = useState<any[]>([]);
  const [activePaper, setActivePaper] = useState<any>(null);
  const [activeExecution, setActiveExecution] = useState<any>(null);
  const [jasonState, setJasonState] = useState<any>(null);
  const [jasonTrades, setJasonTrades] = useState<any[]>([]);

  const [selected, setSelected] = useState<string[]>([]);
  const [switchCandidate, setSwitchCandidate] = useState<string | null>(null);
  const [switchConfirm, setSwitchConfirm] = useState('');
  const [switchMsg, setSwitchMsg] = useState('');
  const [switchBusy, setSwitchBusy] = useState(false);

  const [symbolFilter, setSymbolFilter] = useState('all');
  const [agentFilter, setAgentFilter] = useState('all');
  const [timeFilter, setTimeFilter] = useState<'1h' | '6h' | '24h' | 'all'>('24h');
  const [focusedPacketId, setFocusedPacketId] = useState<number | null>(null);

  const load = async () => {
    const [packetRes, activeRes, execRes, jsState, jsTrades] = await Promise.all([
      getAgentDecisionPackets(500).catch(() => ({ items: [] })),
      getActivePaperModel().catch(() => ({ item: null })),
      getActiveExecutionModel().catch(() => ({ item: null })),
      getJasonState().catch(() => ({ state: null, open_trade: null })),
      getJasonTrades(30).catch(() => ({ items: [] })),
    ]);
    setPackets(packetRes?.items || []);
    setActivePaper(activeRes?.item || null);
    setActiveExecution(execRes?.item || null);
    setJasonState(jsState || null);
    setJasonTrades(jsTrades?.items || []);
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
  }, [filteredPackets]);

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

  const digest = useMemo(() => {
    const totalAgents = rankedModels.length;
    const totalPackets = filteredPackets.length;
    const leader = rankedModels[0] || null;
    const jState = jasonState?.state || {};
    const jOpen = jasonState?.open_trade || null;
    return {
      totalAgents,
      totalPackets,
      leader,
      jBalance: Number(jState.balance_usd || 0),
      jActive: Boolean(jState.active),
      jOpen,
    };
  }, [rankedModels, filteredPackets, jasonState]);

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

      <div className="grid arena-digest-grid" style={{ marginBottom: 12 }}>
        <div className="card glass-card compact arena-active-banner">
          <div className="muted">Active Execution</div>
          <div className="kpi-value" style={{ fontSize: '1.1rem' }}>{activeExecution?.agent_id || 'none selected'}</div>
        </div>
        <div className="card glass-card compact">
          <div className="muted">Agents in view</div>
          <div className="kpi-value" style={{ fontSize: '1.1rem' }}>{digest.totalAgents}</div>
        </div>
        <div className="card glass-card compact">
          <div className="muted">Decision packets</div>
          <div className="kpi-value" style={{ fontSize: '1.1rem' }}>{digest.totalPackets}</div>
        </div>
        <div className="card glass-card compact">
          <div className="muted">Leader now</div>
          <div className="kpi-value" style={{ fontSize: '1.1rem' }}>{digest.leader?.label || 'n/a'}</div>
        </div>
      </div>

      <div className="grid" style={{ gridTemplateColumns: '1.2fr 1fr', marginBottom: 12 }}>
        <div className="card glass-card">
          <h3 style={{ marginTop: 0 }}>What just happened</h3>
          <div className="trace-list">
            {timelinePackets.slice(0, 10).map((p) => (
              <div key={`digest-${p.id}`} className="arena-event-row">
                <div>
                  <strong>{String(p.agent_id || 'unknown')}</strong> {String(p.action || 'n/a').toUpperCase()} {String(p.symbol || 'n/a')}
                  <div className="muted">{p.rationale || 'No rationale provided.'}</div>
                </div>
                <div className="muted">{p.ts ? new Date(Number(p.ts)).toLocaleTimeString() : 'n/a'}</div>
              </div>
            ))}
          </div>
        </div>

        <div className="card glass-card">
          <h3 style={{ marginTop: 0 }}>Jason Snapshot</h3>
          <div className="muted">Running: {digest.jActive ? 'yes' : 'no'}</div>
          <div className="muted">Balance: {digest.jBalance.toFixed(2)} USD</div>
          {digest.jOpen ? (
            <>
              <div className="muted">Open: {digest.jOpen.side?.toUpperCase()} {digest.jOpen.symbol}</div>
              <div className="muted">Leverage: {Number(digest.jOpen.leverage || 0).toFixed(2)}x</div>
              <div className="muted">Entry: {Number(digest.jOpen.entry_price || 0).toFixed(2)}</div>
            </>
          ) : <div className="muted">Open: none</div>}
          <button className="btn" style={{ marginTop: 8 }} onClick={load}>Refresh</button>
        </div>
      </div>

      <div className="card glass-card" style={{ marginBottom: 12 }}>
        <div className="toolbar">
          <button className="btn" onClick={load}>Refresh Arena Data</button>
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

      <div className="arena-grid">
        {rankedModels.length === 0 ? (
          <div className="card glass-card">No decision packets in this filter scope.</div>
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
                <div><span className="muted">Confidence</span><strong>{pct(model.avgConfidence * 100)}</strong></div>
              </div>
              <div className="muted">Symbols: {model.symbols.length > 0 ? model.symbols.join(', ') : 'n/a'}</div>
              <div className="toolbar">
                <button className={`btn ${selected.includes(model.id) ? 'active' : ''}`} onClick={() => toggleSelection(model.id)}>
                  {selected.includes(model.id) ? 'Selected' : 'Compare'}
                </button>
                <button
                  className={`btn ${activeExecution?.agent_id === model.id ? 'active' : ''}`}
                  onClick={() => {
                    if (activeExecution?.agent_id === model.id) return;
                    setSwitchMsg('');
                    setSwitchCandidate(model.id);
                  }}
                  disabled={activeExecution?.agent_id === model.id}
                >
                  {activeExecution?.agent_id === model.id ? 'Active' : 'Set Active'}
                </button>
              </div>
            </article>
          ))
        )}
      </div>

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

      <div className="card table-wrap glass-card" style={{ marginTop: 12 }}>
        <h3 style={{ marginTop: 0 }}>Jason Recent Trades</h3>
        <table className="responsive-table">
          <thead><tr><th>Opened</th><th>Side</th><th>Symbol</th><th>Lev</th><th>Entry</th><th>Status</th><th>PnL</th></tr></thead>
          <tbody>
            {jasonTrades.length === 0 ? <tr><td colSpan={7} className="muted">No trades yet.</td></tr> : jasonTrades.slice(0, 12).map((t) => (
              <tr key={t.id}>
                <td data-label="Opened">{t.opened_at_ms ? new Date(Number(t.opened_at_ms)).toLocaleString() : 'n/a'}</td>
                <td data-label="Side">{String(t.side || '').toUpperCase()}</td>
                <td data-label="Symbol">{t.symbol}</td>
                <td data-label="Lev">{Number(t.leverage || 0).toFixed(1)}x</td>
                <td data-label="Entry">{Number(t.entry_price || 0).toFixed(2)}</td>
                <td data-label="Status">{t.status}</td>
                <td data-label="PnL">{t.realized_pnl_usd == null ? 'n/a' : Number(t.realized_pnl_usd).toFixed(2)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="card glass-card" style={{ marginTop: 12 }}>
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
      </div>
    </section>
  );
}
