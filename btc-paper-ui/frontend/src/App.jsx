import React, { useEffect, useState } from 'react'

const API = 'http://127.0.0.1:8000'
const MODE_ORDER = ['btc_15m_conservative', 'btc_5m_aggressive']

function ModePanel({ modeKey, m, onAck }) {
  const d = m?.latest_decision || {}
  const openPos = (m?.open_positions || [])[0]
  const latestClosed = (m?.closed_trades || []).slice(-1)[0]
  const tradeAge = openPos?.open_time ? Math.max(0, Math.floor((Date.now() - new Date(openPos.open_time).getTime()) / 60000)) : null
  const bid = m?.market_data?.[0]?.bid ?? 0
  const ask = m?.market_data?.[0]?.ask ?? 0
  const spread = m?.market_data?.[0]?.spread ?? 0
  const spreadPct = m?.market_data?.[0]?.spread_pct ?? 0
  const realized = m?.current_pnl?.realized ?? 0
  const unrealized = m?.current_pnl?.unrealized ?? 0
  const totalPnl = Number(realized) + Number(unrealized)
  const equity = 10000 + totalPnl
  const cash = 10000 + realized
  const posQty = openPos?.qty ?? 0
  const notional = openPos ? (openPos.qty * openPos.entry_fill_price) : 0
  return (
    <div className='panel' style={{ marginBottom: 12 }}>
      <h3>{m?.mode_label || modeKey}</h3>
      <div style={{ fontSize: 12, opacity: .85 }}>Timeframe: {m?.timeframe} | Last scan: {m?.latest_scan_time}</div>
      {m?.notify_user && (
        <div style={{ marginTop: 8, border: '1px solid #f85149', padding: 8, borderRadius: 6 }}>
          <strong style={{ color: '#f85149' }}>{m.notify_user.message}</strong>
          <button style={{ marginLeft: 8 }} onClick={() => onAck(modeKey)}>Ack</button>
        </div>
      )}
      <p>Status: <strong>{d.status}</strong> | Regime: {d.regime_label}</p>
      <p>Side: {d.side || '-'} | Entry: {d.entry_price || 0} | SL: {d.stop_loss || 0} | TP: {d.take_profit || 0} | R:R: {d.risk_reward_ratio || 0}</p>
      <p style={{ fontSize: 12 }}>Reason: {d.reason}</p>

      <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:6,margin:'8px 0',fontSize:12}}>
        <div style={{background:'#0d1117',padding:8,borderRadius:6,border:'1px solid #30363d'}}><strong>Cash</strong><div>{cash.toFixed(2)}</div></div>
        <div style={{background:'#0d1117',padding:8,borderRadius:6,border:'1px solid #30363d'}}><strong>Equity</strong><div>{equity.toFixed(2)}</div></div>
        <div style={{background:'#0d1117',padding:8,borderRadius:6,border:'1px solid #30363d'}}><strong>Realized PnL</strong><div>{Number(realized).toFixed(2)}</div></div>
        <div style={{background:'#0d1117',padding:8,borderRadius:6,border:'1px solid #30363d'}}><strong>Unrealized PnL</strong><div>{Number(unrealized).toFixed(2)}</div></div>
        <div style={{background:'#0d1117',padding:8,borderRadius:6,border:'1px solid #30363d'}}><strong>Total PnL</strong><div>{Number(totalPnl).toFixed(2)}</div></div>
        <div style={{background:'#0d1117',padding:8,borderRadius:6,border:'1px solid #30363d'}}><strong>Max Drawdown</strong><div>{Number(m?.mode_stats?.max_drawdown ?? 0).toFixed(2)}</div></div>
      </div>

      <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:6,marginBottom:8,fontSize:12}}>
        <div style={{background:'#0d1117',padding:8,borderRadius:6,border:'1px solid #30363d'}}><strong>Open Size / Notional</strong><div>{posQty} / {Number(notional).toFixed(2)}</div></div>
        <div style={{background:'#0d1117',padding:8,borderRadius:6,border:'1px solid #30363d'}}><strong>Latest Fill</strong><div>{openPos?.entry_fill_price ?? '-'}</div></div>
        <div style={{background:'#0d1117',padding:8,borderRadius:6,border:'1px solid #30363d'}}><strong>Bid / Ask</strong><div>{bid} / {ask}</div></div>
        <div style={{background:'#0d1117',padding:8,borderRadius:6,border:'1px solid #30363d'}}><strong>Spread / %</strong><div>{Number(spread).toFixed(4)} / {Number(spreadPct).toFixed(6)}%</div></div>
      </div>

      <p>Open: {(m?.open_positions || []).length} | Closed: {(m?.closed_trades || []).length} | Pending: {(m?.pending_orders || []).length}</p>
      <div style={{ fontSize: 12 }}>
        WinRate: {m?.mode_stats?.win_rate ?? 0}% | AvgWin: {m?.mode_stats?.average_win ?? 0} | AvgLoss: {m?.mode_stats?.average_loss ?? 0} | MaxDD: {m?.mode_stats?.max_drawdown ?? 0}
      </div>

      <details style={{ marginTop: 8 }}>
        <summary>Mode details</summary>
        <div style={{ fontSize: 12, marginTop: 8 }}>
          <strong>Latest executable decision</strong>
          <div>Side: {d.side || '-'}</div>
          <div>Entry: {d.entry_price || 0}</div>
          <div>Stop Loss: {d.stop_loss || 0}</div>
          <div>Take Profit: {d.take_profit || 0}</div>
          <div>Invalidation: {d.invalidation || '-'}</div>
          <div>Risk/Reward: {d.risk_reward_ratio || 0}</div>
          <div>Reason: {d.reason || '-'}</div>
          <div>Latest scan time: {m?.latest_scan_time || '-'}</div>
          <div>Latest decision time: {m?.latest_decision_time || '-'}</div>

          <div style={{ marginTop: 8 }}><strong>Open trade</strong></div>
          {openPos ? (
            <>
              <div>Fill price: {openPos.entry_fill_price}</div>
              <div>Unrealized PnL: {openPos.unrealized_pnl}</div>
              <div>Open time: {openPos.open_time}</div>
              <div>Age: {tradeAge} min</div>
            </>
          ) : <div>None</div>}

          <div style={{ marginTop: 8 }}><strong>Latest closed trade</strong></div>
          {latestClosed ? (
            <>
              <div>Entry: {latestClosed.entry_fill_price}</div>
              <div>Exit: {latestClosed.close_fill_price}</div>
              <div>Realized PnL: {latestClosed.realized_pnl}</div>
              <div>Close reason: {latestClosed.close_reason}</div>
            </>
          ) : <div>None</div>}
        </div>
      </details>

      <details style={{ marginTop: 6 }}>
        <summary>Recent history ({(m?.history || []).length})</summary>
        <table className='rows' style={{ width: '100%' }}>
          <thead><tr><th>Time</th><th>Status</th><th>Regime</th><th>R:R</th></tr></thead>
          <tbody>
            {(m?.history || []).slice(-8).reverse().map((r, i) => (
              <tr key={i}><td>{r.timestamp}</td><td>{r.status}</td><td>{r.regime_label}</td><td>{r.risk_reward_ratio}</td></tr>
            ))}
          </tbody>
        </table>
      </details>
    </div>
  )
}

export default function App() {
  const [state, setState] = useState(null)
  const [err, setErr] = useState('')

  const load = async () => {
    try {
      const s = await fetch(`${API}/api/state`).then(r => r.json())
      const h = await fetch(`${API}/api/history`).then(r => r.json())
      if (h?.history && typeof h.history === 'object') {
        for (const k of Object.keys(h.history)) {
          if (s?.modes?.[k]) s.modes[k].history = h.history[k]
        }
      }
      setState(s)
      setErr('')
    } catch (e) {
      setErr('Failed to load state')
    }
  }

  const runScanBoth = async () => { await fetch(`${API}/api/run-scan`, { method: 'POST' }); await load() }
  const toggleAuto = async () => { await fetch(`${API}/api/auto-scan`, { method: 'POST' }); await load() }
  const ack = async (mode) => { await fetch(`${API}/api/ack-notify/${mode}`, { method: 'POST' }); await load() }

  useEffect(() => {
    load()
    const t = setInterval(load, 15000)
    return () => clearInterval(t)
  }, [])

  if (!state) return <div className='wrap'>Loading...</div>

  return (
    <div className='wrap'>
      <div className='top'>
        <h2>BTC Paper Dashboard (Parallel Modes)</h2>
        <div style={{ display: 'flex', gap: 8 }}>
          <span className='badge'>PAPER MODE</span>
          <button onClick={runScanBoth}>Run Both Scans</button>
          <button onClick={toggleAuto}>{state.auto_scan ? 'Pause Auto' : 'Resume Auto'}</button>
        </div>
      </div>
      {err && <div className='panel' style={{ color: '#f85149', borderColor: '#f85149' }}>{err}</div>}
      <div className='grid' style={{ gridTemplateColumns: '1fr 1fr' }}>
        {MODE_ORDER.map(k => <ModePanel key={k} modeKey={k} m={state?.modes?.[k]} onAck={ack} />)}
      </div>
    </div>
  )
}
