import React, { useEffect, useState } from 'react'

const API = 'http://127.0.0.1:8000'
const MODE_ORDER = ['btc_15m_conservative', 'btc_5m_aggressive']

function ModePanel({ modeKey, m, onAck }) {
  const d = m?.latest_decision || {}
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
      <p>PnL (R/U): {m?.current_pnl?.realized ?? 0} / {m?.current_pnl?.unrealized ?? 0}</p>
      <p>Open: {(m?.open_positions || []).length} | Closed: {(m?.closed_trades || []).length} | Pending: {(m?.pending_orders || []).length}</p>
      <div style={{ fontSize: 12 }}>
        WinRate: {m?.mode_stats?.win_rate ?? 0}% | AvgWin: {m?.mode_stats?.average_win ?? 0} | AvgLoss: {m?.mode_stats?.average_loss ?? 0} | MaxDD: {m?.mode_stats?.max_drawdown ?? 0}
      </div>
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
