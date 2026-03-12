import React, { useEffect, useRef, useState } from 'react'
import { createChart } from 'lightweight-charts'

const API = window.location.origin.includes('5173') ? 'http://127.0.0.1:8000' : window.location.origin
const MODE_ORDER = ['btc_15m_conservative', 'btc_15m_breakout_retest']
const POLL_MS = 30000

function SharedChart({ state, theme }) {
  const ref = useRef(null)
  const [chartError, setChartError] = useState('')
  const baseMode = state?.modes?.btc_15m_breakout_retest?.market_data?.[0]?.ohlcv?.length
    ? state?.modes?.btc_15m_breakout_retest
    : state?.modes?.btc_15m_conservative

  useEffect(() => {
    const candles = baseMode?.market_data?.[0]?.ohlcv || []
    if (!ref.current || candles.length === 0) {
      setChartError('No candle data available.')
      return
    }

    const container = ref.current
    container.innerHTML = ''

    const isLight = theme === 'light'
    const danger = isLight ? '#b91c1c' : '#f85149'
    try {
      const modeColors = {
        btc_15m_conservative: { entry: '#2563eb', open: '#2563eb', close: '#1d4ed8', sl: '#dc2626', tp: '#16a34a' },
        btc_15m_breakout_retest: { entry: '#a855f7', open: '#a855f7', close: '#7e22ce', sl: '#ef4444', tp: '#22c55e' },
      }

      const chart = createChart(container, {
        width: container.clientWidth || 900,
        height: 320,
        layout: { background: { color: isLight ? '#ffffff' : '#161b22' }, textColor: isLight ? '#111827' : '#e6edf3' },
        grid: { vertLines: { color: isLight ? '#e5e7eb' : '#30363d' }, horzLines: { color: isLight ? '#e5e7eb' : '#30363d' } }
      })
      const s = chart.addCandlestickSeries()
      s.setData(candles.map(c => ({
        time: Math.floor(new Date(c.time).getTime() / 1000),
        open: c.open, high: c.high, low: c.low, close: c.close
      })))

      const markers = []
      MODE_ORDER.forEach((mk) => {
        const m = state?.modes?.[mk]
        const mc = modeColors[mk] || modeColors.btc_15m_conservative
        ;(m?.open_positions || []).forEach((p) => {
          const t = Math.floor(new Date(p.open_time).getTime() / 1000)
          markers.push({ time: t, position: p.side === 'BUY' ? 'belowBar' : 'aboveBar', color: mc.open, shape: 'arrowUp', text: `${mk}:OPEN` })
          markers.push({ time: t, position: p.side === 'BUY' ? 'belowBar' : 'aboveBar', color: mc.entry, shape: 'circle', text: `${mk}:ENTRY` })
          s.createPriceLine({ price: p.entry_fill_price, color: mc.entry, lineStyle: 2, lineWidth: 2, title: `${mk} entry` })
          s.createPriceLine({ price: p.stop_loss, color: mc.sl, lineStyle: 2, lineWidth: 2, title: `${mk} SL` })
          s.createPriceLine({ price: p.take_profit, color: mc.tp, lineStyle: 2, lineWidth: 2, title: `${mk} TP` })
        })
        ;(m?.closed_trades || []).slice(-8).forEach((t) => {
          if (!t.close_time) return
          const tt = Math.floor(new Date(t.close_time).getTime() / 1000)
          if (!Number.isFinite(tt)) return
          markers.push({ time: tt, position: t.side === 'BUY' ? 'aboveBar' : 'belowBar', color: mc.close, shape: 'square', text: `${mk}:CLOSE` })
        })
        const tr = m?.triggers
        if (tr) {
          s.createPriceLine({ price: tr.upper, color: danger, lineStyle: 4, lineWidth: 1, title: 'Upper trigger' })
          s.createPriceLine({ price: tr.lower, color: '#2ea043', lineStyle: 4, lineWidth: 1, title: 'Lower trigger' })
        }
      })

      if (markers.length) s.setMarkers(markers)
      chart.timeScale().fitContent()
      setChartError('')

      const ro = new ResizeObserver(() => {
        chart.applyOptions({ width: container.clientWidth || 900 })
      })
      ro.observe(container)

      return () => {
        ro.disconnect()
        chart.remove()
      }
    } catch (e) {
      setChartError('Chart render failed.')
    }
  }, [state, baseMode, theme])

  const bid = baseMode?.market_data?.[0]?.bid
  const ask = baseMode?.market_data?.[0]?.ask
  const last = baseMode?.market_data?.[0]?.ohlcv?.slice(-1)[0]?.close
  return (
    <div className='panel' style={{ marginBottom: 12 }}>
      <div style={{ fontSize: 12, marginBottom: 6 }}>
        BTC live: <strong>{last ?? '-'}</strong> | Bid/Ask: {bid ?? '-'} / {ask ?? '-'}
      </div>
      <div ref={ref} style={{ minHeight: 320, width: '100%' }} />
      {chartError && <div style={{ marginTop: 8, color: 'var(--danger)' }}>{chartError}</div>}
    </div>
  )
}

function fmt2(x) { return Number(x ?? 0).toFixed(2) }

function prettyStatus(status) {
  return String(status || 'insufficient_data').replaceAll('_', ' ')
}

function scoreMetaForMode(m) {
  const selected = m?.shadow_routing?.selected_strategy
  const candidates = m?.shadow_routing?.ranked_candidates || []
  const hit = candidates.find(c => c.strategy_key === m?.mode)
  const score = selected === m?.mode ? (m?.shadow_routing?.selected_score ?? hit?.score) : hit?.score
  const eligible = hit?.eligible
  const reason = hit?.reason || m?.shadow_routing?.selection_reason || 'score unavailable'

  if (!hit) return { label: 'score unavailable', reason: 'No shadow-routing candidate data for this strategy.', numeric: null }
  if (eligible === false || score === -9999 || score === -9999.0) return { label: 'not eligible', reason, numeric: null }
  if (m?.strategy_status === 'insufficient_data') return { label: 'insufficient data', reason, numeric: score ?? null }
  if (typeof score !== 'number' || Number.isNaN(score)) return { label: 'score unavailable', reason, numeric: null }
  return { label: fmt2(score), reason, numeric: score }
}

function StrategyScorecard({ m }) {
  const reg = m?.current_regime || {}
  const sr = m?.strategy_registry_entry || {}
  const metrics = m?.strategy_metrics || {}
  const learn = m?.learning_summary || {}
  const patterns = learn?.failure_patterns || {}
  const scoreMeta = scoreMetaForMode(m)
  return (
    <div className='panel' style={{ marginBottom: 12, background: 'var(--cardSoft)' }}>
      <h4 style={{ marginTop: 0, marginBottom: 8 }}>{sr.label || m?.mode}</h4>
      <div style={{ display:'grid', gridTemplateColumns:'repeat(3, 1fr)', gap:8, fontSize:12 }}>
        <div><strong>Strategy</strong><div>{m?.mode}</div></div>
        <div><strong>Family</strong><div>{sr.family || '-'}</div></div>
        <div><strong>Status</strong><div>{prettyStatus(m?.strategy_status)}</div></div>
        <div><strong>Current regime</strong><div>{reg.regime || '-'}</div></div>
        <div><strong>Regime confidence</strong><div>{reg.confidence ?? '-'}</div></div>
        <div><strong>Strategy score</strong><div>{scoreMeta.label}</div><div style={{ opacity: 0.75 }}>{scoreMeta.reason}</div></div>
        <div><strong>Win rate</strong><div>{fmt2(metrics.win_rate)}%</div></div>
        <div><strong>Expectancy</strong><div>{fmt2(metrics.expectancy)}</div></div>
        <div><strong>Net realized PnL</strong><div>{fmt2(metrics.realized_pnl)}</div></div>
        <div><strong>Net unrealized PnL</strong><div>{fmt2(metrics.unrealized_pnl)}</div></div>
        <div><strong>Total fees</strong><div>{fmt2(metrics.total_fees)}</div></div>
        <div><strong>Fee drag</strong><div>{fmt2(metrics.fee_drag_pct)}%</div></div>
        <div><strong>Best regime</strong><div>{learn.best_regime || '-'}</div></div>
        <div><strong>Worst regime</strong><div>{learn.worst_regime || '-'}</div></div>
        <div><strong>Shadow-selected</strong><div>{m?.shadow_routing?.selected_strategy || '-'}</div></div>
      </div>
      <div style={{ marginTop: 10, fontSize: 12 }}>
        <strong>Learning summary:</strong> {learn.what_works || '-'} | <strong>Weaknesses:</strong> {learn.what_fails || '-'}
      </div>
      <div style={{ marginTop: 6, fontSize: 12 }}>
        <strong>Failure patterns:</strong> no-edge {patterns.no_edge_repeats ?? 0}, fee-drag {patterns.fee_drag_destroying_edge ?? 0}, TP-missed→SL {patterns.tp_missed_then_reversed_to_sl ?? 0}, mismatch {patterns.regime_mismatch ?? 0}
      </div>
    </div>
  )
}

function RuntimePanel({ state }) {
  const info = state?.runtime_info || {}
  return (
    <div className='panel' style={{ marginBottom: 12 }}>
      <h3>Runtime / model split</h3>
      <div style={{ fontSize: 13 }}>
        <div><strong>Agent/runtime model:</strong> {info.agent_runtime_model || 'unknown'}</div>
        <div><strong>GPT-5.4 is used for:</strong> {info.gpt_5_4_used_for || 'unknown'}</div>
        <div><strong>Backend logic:</strong> {info.backend_logic || 'rule-based'}</div>
        <div><strong>Concurrency cap:</strong> {info.max_open_positions_per_mode ?? '-' } open BTC paper positions per mode</div>
      </div>
    </div>
  )
}

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
  const grossRealized = m?.current_pnl?.gross_realized ?? m?.mode_stats?.gross_realized_pnl ?? realized
  const grossUnrealized = m?.current_pnl?.gross_unrealized ?? m?.mode_stats?.gross_unrealized_pnl ?? unrealized
  const totalFees = m?.current_pnl?.total_fees ?? m?.mode_stats?.total_fees ?? 0
  const feeModel = m?.current_pnl?.fee_model ?? m?.mode_stats?.fee_model ?? '-'
  const feePct = m?.current_pnl?.fee_pct ?? m?.mode_stats?.fee_pct ?? 0
  const feeDragPct = m?.current_pnl?.fee_drag_pct_of_gross_pnl ?? m?.mode_stats?.fee_drag_pct_of_gross_pnl ?? 0
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
        <div style={{ marginTop: 8, border: '1px solid var(--danger)', padding: 8, borderRadius: 6 }}>
          <strong style={{ color: 'var(--danger)' }}>{m.notify_user.message}</strong>
          <button style={{ marginLeft: 8 }} onClick={() => onAck(modeKey)}>Ack</button>
        </div>
      )}
      <p>Status: <strong>{d.status}</strong> | Regime: {d.regime_label}</p>
      <p>Side: {d.side || '-'} | Entry: {d.entry_price || 0} | SL: {d.stop_loss || 0} | TP: {d.take_profit || 0} | R:R: {d.risk_reward_ratio || 0}</p>
      <p style={{ fontSize: 12 }}>Reason: {d.reason}</p>

      <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:6,margin:'8px 0',fontSize:12}}>
        <div style={{background:'var(--cardSoft)',padding:8,borderRadius:6,border:'1px solid var(--border)'}}><strong>Cash</strong><div>{fmt2(cash)}</div></div>
        <div style={{background:'var(--cardSoft)',padding:8,borderRadius:6,border:'1px solid var(--border)'}}><strong>Equity</strong><div>{fmt2(equity)}</div></div>
        <div style={{background:'var(--cardSoft)',padding:8,borderRadius:6,border:'1px solid var(--border)'}}><strong>Gross Realized PnL</strong><div>{fmt2(grossRealized)}</div></div>
        <div style={{background:'var(--cardSoft)',padding:8,borderRadius:6,border:'1px solid var(--border)'}}><strong>Net Realized PnL</strong><div>{fmt2(realized)}</div></div>
        <div style={{background:'var(--cardSoft)',padding:8,borderRadius:6,border:'1px solid var(--border)'}}><strong>Gross Unrealized PnL</strong><div>{fmt2(grossUnrealized)}</div></div>
        <div style={{background:'var(--cardSoft)',padding:8,borderRadius:6,border:'1px solid var(--border)'}}><strong>Net Unrealized PnL</strong><div>{fmt2(unrealized)}</div></div>
        <div style={{background:'var(--cardSoft)',padding:8,borderRadius:6,border:'1px solid var(--border)'}}><strong>Total Fees Paid</strong><div>{fmt2(totalFees)}</div></div>
        <div style={{background:'var(--cardSoft)',padding:8,borderRadius:6,border:'1px solid var(--border)'}}><strong>Fee Model / %</strong><div>{feeModel} / {fmt2(feePct)}%</div></div>
        <div style={{background:'var(--cardSoft)',padding:8,borderRadius:6,border:'1px solid var(--border)'}}><strong>Fee Drag % Gross PnL</strong><div>{fmt2(feeDragPct)}%</div></div>
        <div style={{background:'var(--cardSoft)',padding:8,borderRadius:6,border:'1px solid var(--border)'}}><strong>Total PnL (Net)</strong><div>{fmt2(totalPnl)}</div></div>
        <div style={{background:'var(--cardSoft)',padding:8,borderRadius:6,border:'1px solid var(--border)'}}><strong>Max Drawdown</strong><div>{fmt2(m?.mode_stats?.max_drawdown ?? 0)}</div></div>
      </div>

      <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:6,marginBottom:8,fontSize:12}}>
        <div style={{background:'var(--cardSoft)',padding:8,borderRadius:6,border:'1px solid var(--border)'}}><strong>Open Size / Notional</strong><div>{posQty} / {Number(notional).toFixed(2)}</div></div>
        <div style={{background:'var(--cardSoft)',padding:8,borderRadius:6,border:'1px solid var(--border)'}}><strong>Latest Fill</strong><div>{openPos?.entry_fill_price ?? '-'}</div></div>
        <div style={{background:'var(--cardSoft)',padding:8,borderRadius:6,border:'1px solid var(--border)'}}><strong>Bid / Ask</strong><div>{bid} / {ask}</div></div>
        <div style={{background:'var(--cardSoft)',padding:8,borderRadius:6,border:'1px solid var(--border)'}}><strong>Spread / %</strong><div>{Number(spread).toFixed(4)} / {Number(spreadPct).toFixed(6)}%</div></div>
      </div>

      <p>Open: {(m?.open_positions || []).length} / {(m?.execution_limits?.max_open_positions_per_mode || m?.max_open_positions_per_mode || 2)} | Closed: {(m?.closed_trades || []).length} | Pending: {(m?.pending_orders || []).length}</p>
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
              <div>Entry fee: {openPos.entry_fee ?? '-'}</div>
              <div>Gross unrealized PnL: {openPos.gross_unrealized_pnl ?? '-'}</div>
              <div>Net unrealized PnL: {openPos.net_unrealized_pnl ?? openPos.unrealized_pnl ?? '-'}</div>
              <div>Unrealized PnL (net): {openPos.unrealized_pnl}</div>
              <div>Open time: {openPos.open_time}</div>
              <div>Age: {tradeAge} min</div>
            </>
          ) : <div>None</div>}

          <div style={{ marginTop: 8 }}><strong>Latest closed trade</strong></div>
          {latestClosed ? (
            <>
              <div>Entry: {latestClosed.entry_fill_price}</div>
              <div>Exit: {latestClosed.close_fill_price}</div>
              <div>Gross realized PnL: {latestClosed.gross_realized_pnl ?? '-'}</div>
              <div>Net realized PnL: {latestClosed.net_realized_pnl ?? latestClosed.realized_pnl}</div>
              <div>Entry fee: {latestClosed.entry_fee ?? '-'}</div>
              <div>Close fee: {latestClosed.close_fee ?? '-'}</div>
              <div>Total fees: {latestClosed.total_fees ?? '-'}</div>
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
  const [theme, setTheme] = useState('dark')

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
    let t
    const schedule = () => {
      clearInterval(t)
      if (!document.hidden) t = setInterval(load, POLL_MS)
    }
    load()
    schedule()
    const onVis = () => {
      if (!document.hidden) load()
      schedule()
    }
    document.addEventListener('visibilitychange', onVis)
    return () => {
      clearInterval(t)
      document.removeEventListener('visibilitychange', onVis)
    }
  }, [])

  if (!state) return <div className='wrap'>Loading...</div>

  return (
    <div className={`wrap theme-${theme}`}>
      <div className='top'>
        <h2>BTC Paper Dashboard (15m Baseline vs 15m Experiment)</h2>
        <div style={{ display: 'flex', gap: 8 }}>
          <span className='badge'>PAPER MODE</span>
          <button onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}>{theme === 'dark' ? 'Light' : 'Dark'}</button>
          <button onClick={runScanBoth}>Run Both Scans</button>
          <button onClick={toggleAuto}>{state.auto_scan ? 'Pause Auto' : 'Resume Auto'}</button>
        </div>
      </div>
      {err && <div className='panel' style={{ color: 'var(--danger)', borderColor: 'var(--danger)' }}>{err}</div>}
      <RuntimePanel state={state} />
      <SharedChart state={state} theme={theme} />
      <div className='grid' style={{ gridTemplateColumns: '1fr 1fr', marginBottom: 12 }}>
        {MODE_ORDER.map(k => <StrategyScorecard key={`score-${k}`} m={state?.modes?.[k]} />)}
      </div>
      <div className='grid' style={{ gridTemplateColumns: '1fr 1fr' }}>
        {MODE_ORDER.map(k => <ModePanel key={k} modeKey={k} m={state?.modes?.[k]} onAck={ack} />)}
      </div>
    </div>
  )
}
