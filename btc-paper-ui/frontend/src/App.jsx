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

function fmtLA(ts) {
  if (!ts) return '-'
  const d = new Date(ts)
  if (Number.isNaN(d.getTime())) return String(ts)
  return new Intl.DateTimeFormat('en-US', {
    timeZone: 'America/Los_Angeles',
    year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit', second: '2-digit',
    hour12: true,
    timeZoneName: 'short',
  }).format(d)
}

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

function HyperliquidPanel({ hstate, onScan, onMockOpen }) {
  if (!hstate) return null
  const latest = hstate.latest || {}
  const market = latest.market || {}
  const candleCount = (latest.candles || []).length
  const regime = latest.regime || {}
  const risk = hstate.risk_limits || {}
  const fees = hstate.fee_model || {}
  const feeAssumption = hstate.execution_fee_assumption || {}
  const activeStrategyKey = latest.active_strategy_key || hstate.active_strategy_key
  const activeStrategy = latest.active_strategy_entry || (hstate.strategy_registry || {})[activeStrategyKey] || {}
  const metrics = (hstate.metrics || {}).strategy_overall?.[activeStrategyKey] || {}
  const positions = hstate.positions || []
  const closedTrades = hstate.closed_trades || []
  const exposure = positions.reduce((s, p) => s + Number(p.entry_price || 0) * Number(p.qty || 0), 0)
  const marginUsed = positions.reduce((s, p) => s + Number(p.margin_used || 0), 0)
  const freeCollateral = Math.max(0, 1000 - marginUsed)

  const PAPER_START_BALANCE = 1000
  const realizedPnl = closedTrades.reduce((s, t) => s + Number(t.net_realized_pnl ?? t.realized_pnl ?? 0), 0)
  const unrealizedPnl = positions.reduce((s, p) => s + Number(p.unrealized_pnl_net ?? p.unrealized_pnl ?? 0), 0)
  const netPnl = realizedPnl + unrealizedPnl
  const totalFees = closedTrades.reduce((s, t) => s + Number(t.estimated_total_fees ?? t.total_fees ?? 0), 0) + positions.reduce((s, p) => s + Number(p.estimated_total_fees ?? 0), 0)
  const equity = PAPER_START_BALANCE + netPnl

  const pnlColor = (v) => (Number(v) > 0 ? '#16a34a' : Number(v) < 0 ? '#dc2626' : 'inherit')

  return (
    <div className='panel' style={{ marginBottom: 12, borderColor: '#7e22ce' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h3 style={{ margin: 0 }}>Hyperliquid Futures Paper Track</h3>
        <span className='badge'>PAPER ONLY · NO LIVE EXECUTION</span>
      </div>
      <div style={{ fontSize: 12, marginTop: 6 }}>
        <strong>Track:</strong> {hstate.track} | <strong>Symbol:</strong> {hstate.symbol} | <strong>Latest:</strong> {fmtLA(latest.timestamp)}
      </div>
      <div style={{ fontSize: 12, marginTop: 4 }}>
        <strong>Market source:</strong> {latest.market_source || 'unknown'} | <strong>Candles loaded:</strong> {candleCount}
      </div>
      <div style={{ fontSize: 12, marginTop: 4 }}>
        <strong>Active strategy:</strong> {activeStrategyKey || '-'} | <strong>Family:</strong> {activeStrategy.family || '-'} | <strong>Status:</strong> {activeStrategy.status || '-'}
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 8, marginTop: 10, fontSize: 12 }}>
        <div><strong>Leverage (default)</strong><div>{hstate.leverage_default}x</div></div>
        <div><strong>Margin used</strong><div>{fmt2(marginUsed)}</div></div>
        <div><strong>Free collateral*</strong><div>{fmt2(freeCollateral)}</div></div>
        <div><strong>Regime</strong><div>{regime.regime || '-'}</div></div>
        <div><strong>Regime confidence</strong><div>{regime.confidence ?? '-'}</div></div>
        <div><strong>Decision</strong><div>{latest?.decision?.status || '-'}</div></div>
        <div><strong>Maker fee (bps)</strong><div>{fees.maker_bps ?? '-'}</div></div>
        <div><strong>Taker fee (bps)</strong><div>{fees.taker_bps ?? '-'}</div></div>
        <div><strong>Fee source</strong><div>{fees.fee_source || '-'}</div></div>
        <div><strong>Funding mode</strong><div>{fees.funding_mode || '-'}</div></div>
        <div><strong>Funding placeholder (bps/8h)</strong><div>{fees.funding_rate_placeholder_bps_8h ?? '-'}</div></div>
        <div><strong>PnL fee assumption</strong><div>{feeAssumption.entry_liquidity || '-'} / {feeAssumption.exit_liquidity || '-'}</div></div>
        <div><strong>Exposure used</strong><div>{fmt2(exposure)}</div></div>
        <div><strong>Max exposure</strong><div>{fmt2(risk.max_total_exposure_usd ?? 0)}</div></div>
        <div><strong>Max position notional</strong><div>{fmt2(risk.max_position_notional_usd ?? 0)}</div></div>
        <div><strong>Max positions</strong><div>{risk.max_positions ?? '-'}</div></div>
        <div><strong>Max leverage</strong><div>{risk.max_leverage ?? '-'}x</div></div>
        <div><strong>Per-position risk cap</strong><div>{risk.max_risk_per_position_pct ?? '-'}%</div></div>
      </div>

      <div style={{ marginTop: 10, fontSize: 12, background: 'var(--cardSoft)', padding: 8, borderRadius: 6, border: '1px solid var(--border)' }}>
        <strong>Strategy learning snapshot</strong>
        <div>Opened: {metrics.total_opened ?? 0} | Closed: {metrics.total_closed ?? 0} | Open: {metrics.open_positions ?? 0}</div>
        <div>TP / SL / STALE: {metrics.tp_closes ?? 0} / {metrics.sl_closes ?? 0} / {metrics.time_exit_stale_closes ?? 0}</div>
        <div>Net realized: {fmt2(metrics.net_realized_pnl)} | Net unrealized: {fmt2(metrics.net_unrealized_pnl)} | Fees: {fmt2(metrics.total_fees)} | Fee drag: {fmt2(metrics.fee_drag_pct)}%</div>
        <div>Expectancy (net): {fmt2(metrics.expectancy_net)} | Median time-to-close: {metrics.median_time_to_close_min ?? 0} min</div>
      </div>

      <div style={{ marginTop: 10, fontSize: 12, background: 'var(--cardSoft)', padding: 8, borderRadius: 6, border: '1px solid var(--border)' }}>
        <strong>Paper account summary (simulator baseline)</strong>
        <div style={{ display:'grid', gridTemplateColumns:'repeat(3, 1fr)', gap:8, marginTop:6 }}>
          <div><strong>Starting balance</strong><div>{fmt2(PAPER_START_BALANCE)}</div></div>
          <div><strong>Realized PnL</strong><div style={{ color: pnlColor(realizedPnl) }}>{fmt2(realizedPnl)}</div></div>
          <div><strong>Unrealized PnL</strong><div style={{ color: pnlColor(unrealizedPnl) }}>{fmt2(unrealizedPnl)}</div></div>
          <div><strong>Net PnL</strong><div style={{ color: pnlColor(netPnl) }}>{fmt2(netPnl)}</div></div>
          <div><strong>Total fees</strong><div>{fmt2(totalFees)}</div></div>
          <div><strong>Current equity</strong><div style={{ color: pnlColor(netPnl) }}>{fmt2(equity)}</div></div>
        </div>
      </div>

      <div style={{ marginTop: 10 }}>
        <button onClick={onScan}>Run Hyperliquid Mock Scan</button>
        <button style={{ marginLeft: 8 }} onClick={onMockOpen}>Mock Open Paper Position</button>
      </div>

      <details style={{ marginTop: 10 }}>
        <summary>Open futures paper positions ({positions.length})</summary>
        <table className='rows' style={{ width: '100%' }}>
          <thead>
            <tr>
              <th>Side</th><th>Qty</th><th>Entry</th><th>Leverage</th><th>Margin</th><th>Liq. est</th><th>Fee mode</th><th>Fees est</th><th>Open time</th>
            </tr>
          </thead>
          <tbody>
            {positions.slice(-10).map((p, i) => (
              <tr key={i}>
                <td>{p.side}</td><td>{p.qty}</td><td>{p.entry_price}</td><td>{p.leverage}x</td><td>{p.margin_used}</td><td>{p.liquidation_price_estimate}</td><td>{p.entry_liquidity || '-'} / {p.exit_liquidity || '-'}</td><td>{p.estimated_total_fees}</td><td>{fmtLA(p.open_time)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>

      <details style={{ marginTop: 10 }}>
        <summary>Closed futures trades PnL ({closedTrades.length})</summary>
        <table className='rows' style={{ width: '100%' }}>
          <thead>
            <tr>
              <th>Close time</th><th>Reason</th><th>Gross PnL</th><th>Fees</th><th>Net PnL</th><th>Return %</th>
            </tr>
          </thead>
          <tbody>
            {closedTrades.slice(-12).reverse().map((t, i) => {
              const gross = Number(t.gross_realized_pnl ?? 0)
              const feesPaid = Number(t.estimated_total_fees ?? t.total_fees ?? 0)
              const net = Number(t.net_realized_pnl ?? t.realized_pnl ?? 0)
              const entryNotional = Number(t.entry_price ?? 0) * Number(t.qty ?? 0)
              const retPct = entryNotional > 0 ? (net / entryNotional) * 100 : null
              return (
                <tr key={i}>
                  <td>{fmtLA(t.close_time)}</td>
                  <td>{t.close_reason || '-'}</td>
                  <td style={{ color: pnlColor(gross) }}>{fmt2(gross)}</td>
                  <td>{fmt2(feesPaid)}</td>
                  <td style={{ color: pnlColor(net), fontWeight: 700 }}>{fmt2(net)}</td>
                  <td style={{ color: pnlColor(retPct ?? 0) }}>{retPct == null ? '-' : `${fmt2(retPct)}%`}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </details>

      <div style={{ fontSize: 11, opacity: 0.75, marginTop: 6 }}>*Free collateral is a simulator placeholder estimate for paper training view.</div>
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
  const allHistory = m?.history || []
  const lifecycleRows = allHistory.filter(r => ['PAPER_TRADE_OPEN', 'PAPER_TRADE_CLOSED'].includes(r?.status))
  const diagRows = allHistory.filter(r => ['WAIT', 'REJECT'].includes(r?.status))
  const diagCounts = diagRows.reduce((acc, r) => {
    const key = `${r?.status || 'UNKNOWN'}|${r?.reason || r?.regime_label || 'n/a'}`
    acc[key] = (acc[key] || 0) + 1
    return acc
  }, {})
  const diagTop = Object.entries(diagCounts).sort((a, b) => b[1] - a[1]).slice(0, 5)
  return (
    <div className='panel' style={{ marginBottom: 12 }}>
      <h3>{m?.mode_label || modeKey}</h3>
      <div style={{ fontSize: 12, opacity: .85 }}>Timeframe: {m?.timeframe} | Last scan: {fmtLA(m?.latest_scan_time)}</div>
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
          <div>Latest scan time: {fmtLA(m?.latest_scan_time)}</div>
          <div>Latest decision time: {fmtLA(m?.latest_decision_time)}</div>

          <div style={{ marginTop: 8 }}><strong>Open trade</strong></div>
          {openPos ? (
            <>
              <div>Fill price: {openPos.entry_fill_price}</div>
              <div>Entry fee: {openPos.entry_fee ?? '-'}</div>
              <div>Gross unrealized PnL: {openPos.gross_unrealized_pnl ?? '-'}</div>
              <div>Net unrealized PnL: {openPos.net_unrealized_pnl ?? openPos.unrealized_pnl ?? '-'}</div>
              <div>Unrealized PnL (net): {openPos.unrealized_pnl}</div>
              <div>Open time: {fmtLA(openPos.open_time)}</div>
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
              <div>Close time: {fmtLA(latestClosed.close_time)}</div>
              <div>Close reason: {latestClosed.close_reason}</div>
            </>
          ) : <div>None</div>}
        </div>
      </details>

      <details style={{ marginTop: 6 }}>
        <summary>Recent lifecycle history ({lifecycleRows.length})</summary>
        <table className='rows' style={{ width: '100%' }}>
          <thead><tr><th>Time</th><th>Status</th><th>Regime</th><th>R:R</th></tr></thead>
          <tbody>
            {lifecycleRows.slice(-8).reverse().map((r, i) => (
              <tr key={i}><td>{fmtLA(r.timestamp)}</td><td>{r.status}</td><td>{r.regime_label}</td><td>{r.risk_reward_ratio}</td></tr>
            ))}
          </tbody>
        </table>
      </details>

      <details style={{ marginTop: 6 }}>
        <summary>Scan diagnostics (WAIT/REJECT summary)</summary>
        <div style={{ fontSize: 12, marginTop: 8 }}>
          <div>Window size: {allHistory.length}</div>
          <div>WAIT count: {diagRows.filter(r => r.status === 'WAIT').length} | REJECT count: {diagRows.filter(r => r.status === 'REJECT').length}</div>
          <div style={{ marginTop: 6 }}><strong>Top reasons</strong></div>
          <ul style={{ margin: '4px 0 0 18px' }}>
            {diagTop.length ? diagTop.map(([k, v], idx) => {
              const [status, reason] = k.split('|')
              return <li key={idx}>{status}: {reason} ({v})</li>
            }) : <li>No WAIT/REJECT rows in current window.</li>}
          </ul>
        </div>
      </details>
    </div>
  )
}

export default function App() {
  const [state, setState] = useState(null)
  const [hyperState, setHyperState] = useState(null)
  const [err, setErr] = useState('')
  const [theme, setTheme] = useState('dark')

  const load = async () => {
    try {
      const s = await fetch(`${API}/api/state`).then(r => r.json())
      const h = await fetch(`${API}/api/history`).then(r => r.json())
      const hs = await fetch(`${API}/api/hyperliquid/state`).then(r => r.json())
      if (h?.history && typeof h.history === 'object') {
        for (const k of Object.keys(h.history)) {
          if (s?.modes?.[k]) s.modes[k].history = h.history[k]
        }
      }
      setState(s)
      setHyperState(hs)
      setErr('')
    } catch (e) {
      setErr('Failed to load state')
    }
  }

  const runScanBoth = async () => { await fetch(`${API}/api/run-scan`, { method: 'POST' }); await load() }
  const runHyperScan = async () => { await fetch(`${API}/api/hyperliquid/run-scan`, { method: 'POST' }); await load() }
  const mockHyperOpen = async () => { await fetch(`${API}/api/hyperliquid/mock-open?side=BUY&qty=0.01&leverage=2`, { method: 'POST' }); await load() }
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
      <div className='grid' style={{ gridTemplateColumns: '1fr 1fr', marginBottom: 12 }}>
        <div>
          <div className='panel' style={{ marginBottom: 8 }}><strong>Kraken Baseline Track</strong> <span className='badge'>PAPER MODE</span></div>
          <SharedChart state={state} theme={theme} />
        </div>
        <div>
          <HyperliquidPanel hstate={hyperState} onScan={runHyperScan} onMockOpen={mockHyperOpen} />
        </div>
      </div>
      <div className='grid' style={{ gridTemplateColumns: '1fr 1fr', marginBottom: 12 }}>
        {MODE_ORDER.map(k => <StrategyScorecard key={`score-${k}`} m={state?.modes?.[k]} />)}
      </div>
      <div className='grid' style={{ gridTemplateColumns: '1fr 1fr' }}>
        {MODE_ORDER.map(k => <ModePanel key={k} modeKey={k} m={state?.modes?.[k]} onAck={ack} />)}
      </div>
    </div>
  )
}
