import React, { useEffect, useRef, useState } from 'react'
import { createChart } from 'lightweight-charts'

const API = window.location.origin.includes('5173') ? 'http://127.0.0.1:8000' : window.location.origin
const MODE_ORDER = ['btc_15m_conservative', 'btc_15m_conservative_netedge_v1']
const POLL_MS = 30000
const PAGES = ['Overview', 'Hyperliquid', 'Kraken', 'Research', 'News / Logs']
const PAGE_SUBTITLES = {
  Overview: 'Cross-exchange paper snapshot with quick risk + decision context.',
  Hyperliquid: 'ETH-perp paper learner details, positions, and execution diagnostics.',
  Kraken: 'BTC paper baseline + learner side-by-side execution view.',
  Research: 'Comparative strategy health and evaluation snapshots across tracks.',
  'News / Logs': 'Advisory narrative and recent scan/lifecycle logs by exchange.',
}

const UI_MODE_NAME_MAP = {
  btc_15m_conservative: { display: 'Kraken BTC 15m Baseline', badge: 'Frozen Reference' },
  btc_15m_conservative_netedge_v1: { display: 'Kraken BTC 15m Net-Edge Learner', badge: 'Active Learner (Paper)' },
  hl_15m_trend_follow: { display: 'Hyperliquid ETH Trend Reference', badge: 'Shadow Reference' },
  hl_15m_trend_follow_momo_gate_v1: { display: 'Hyperliquid ETH Trend Learner (Momentum Gate)', badge: 'Active Learner (Paper)' },
}

function modeUiMeta(rawKey, backendLabel) {
  const mapped = UI_MODE_NAME_MAP[rawKey] || {}
  return {
    displayName: mapped.display || backendLabel || rawKey || '-',
    badge: mapped.badge || null,
    rawKey: rawKey || '-',
  }
}

function SharedChart({ state, theme, compact = false }) {
  const ref = useRef(null)
  const [chartError, setChartError] = useState('')
  const baseMode = state?.modes?.btc_15m_breakout_retest?.market_data?.[0]?.ohlcv?.length
    ? state?.modes?.btc_15m_breakout_retest
    : state?.modes?.btc_15m_conservative

  const cssVar = (name, fallback = '') => {
    const root = document.querySelector('.wrap') || document.documentElement
    const val = getComputedStyle(root).getPropertyValue(name).trim()
    return val || fallback
  }

  useEffect(() => {
    const candles = baseMode?.market_data?.[0]?.ohlcv || []
    if (!ref.current || candles.length === 0) {
      setChartError('No candle data available.')
      return
    }

    const container = ref.current
    container.innerHTML = ''

    const danger = cssVar('--danger', '#EF4444')
    const success = cssVar('--success', '#22C55E')
    const accent = cssVar('--accent', '#3B82F6')
    const accentAlt = cssVar('--accent-alt', '#22D3EE')
    const chartText = cssVar('--text', '#EAF1FF')
    const chartBg = cssVar('--surface', '#0D1424')
    const chartGrid = cssVar('--border', '#1E2A44')
    try {
      const modeColors = {
        btc_15m_conservative: { entry: accent, open: accent, close: accentAlt, sl: danger, tp: success },
        btc_15m_conservative_netedge_v1: { entry: accentAlt, open: accentAlt, close: accent, sl: danger, tp: success },
      }

      const chart = createChart(container, {
        width: container.clientWidth || 900,
        height: compact ? 220 : 320,
        layout: { background: { color: chartBg }, textColor: chartText },
        grid: { vertLines: { color: chartGrid }, horzLines: { color: chartGrid } }
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
          s.createPriceLine({ price: tr.lower, color: success, lineStyle: 4, lineWidth: 1, title: 'Lower trigger' })
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
  }, [state, baseMode, theme, compact])

  const bid = baseMode?.market_data?.[0]?.bid
  const ask = baseMode?.market_data?.[0]?.ask
  const last = baseMode?.market_data?.[0]?.ohlcv?.slice(-1)[0]?.close
  return (
    <div className='panel' style={{ marginBottom: 12 }}>
      <div style={{ fontSize: 12, marginBottom: 6 }}>
        BTC live: <strong>{last ?? '-'}</strong> | Bid/Ask: {bid ?? '-'} / {ask ?? '-'}
      </div>
      <div ref={ref} style={{ minHeight: compact ? 220 : 320, width: '100%' }} />
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

function strategyConfidence({ closed = 0, bestRegimeSample = 0, expectancy = 0, feeDrag = 0 }) {
  const sampleScore = Math.min(1, closed / 30)
  const regimeScore = Math.min(1, bestRegimeSample / 10)
  const stability = Math.max(0, Math.min(1, (expectancy > 0 ? 1 : 0.5) * (feeDrag <= 100 ? 1 : 0.6)))
  return Math.round((sampleScore * 0.4 + regimeScore * 0.3 + stability * 0.3) * 100)
}

function ScoreboardTable({ rows }) {
  return (
    <div className='panel' style={{ marginBottom: 12 }}>
      <h3 style={{ marginTop: 0 }}>Active Bot Scoreboard (4-bot view)</h3>
      <TableWrap>
        <table className='rows' style={{ width: '100%' }}>
          <thead>
            <tr>
              <th>Bot</th><th>Badge</th><th>Group</th><th>Status</th><th>Sample</th><th>Expectancy (net)</th><th>Fee drag %</th><th>Net realized</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={i}>
                <td title={`Internal key: ${r.key}`}>
                  <div>{r.displayName}</div>
                  <div style={{ fontSize: 11, opacity: 0.7 }}>{r.key}</div>
                </td>
                <td>{r.badge ? <span className='badge'>{r.badge}</span> : '-'}</td>
                <td>{r.symbol === 'BTC/USD' ? 'Kraken' : 'Hyperliquid'}</td>
                <td>{r.status}</td>
                <td>{r.closed}</td>
                <td>{fmt2(r.expectancy)}</td>
                <td>{fmt2(r.feeDrag)}</td>
                <td>{fmt2(r.netRealized)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </TableWrap>
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

function NewsPanel({ news, compact = false }) {
  if (!news) return null
  const btc = news.btc || {}
  const eth = news.eth || {}
  return (
    <div className='panel' style={{ marginBottom: 12 }}>
      <h3>{compact ? 'News advisory (compact)' : 'News context (advisory)'}</h3>
      <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:8, fontSize:12 }}>
        <div style={{ background:'var(--cardSoft)', padding:8, borderRadius:6, border:'1px solid var(--border)' }}>
          <strong>BTC</strong>
          <div>Risk: {btc.news_risk || '-'}</div>
          <div>Bias: {btc.news_bias || '-'}</div>
          <div>Confidence: {btc.source_confidence || '-'}</div>
        </div>
        <div style={{ background:'var(--cardSoft)', padding:8, borderRadius:6, border:'1px solid var(--border)' }}>
          <strong>ETH</strong>
          <div>Risk: {eth.news_risk || '-'}</div>
          <div>Bias: {eth.news_bias || '-'}</div>
          <div>Confidence: {eth.source_confidence || '-'}</div>
        </div>
      </div>
      <div style={{ marginTop:8, fontSize:12 }}><strong>Summary:</strong> {news.summary || '-'}</div>
      {!compact && <div style={{ marginTop:4, fontSize:12 }}><strong>Why it matters:</strong> {news.why_it_matters || '-'}</div>}
    </div>
  )
}

function AlertStrip({ state, onAck }) {
  const alerts = MODE_ORDER
    .map((k) => ({ mode: k, msg: state?.modes?.[k]?.notify_user?.message }))
    .filter((x) => x.msg)

  if (!alerts.length) {
    return (
      <div className='panel' style={{ marginBottom: 12, fontSize: 12 }}>
        <strong>Alerts:</strong> no active alerts.
      </div>
    )
  }

  return (
    <div className='panel' style={{ marginBottom: 12, borderColor: 'var(--danger)' }}>
      <strong style={{ fontSize: 12 }}>Alerts</strong>
      <div style={{ display: 'grid', gap: 8, marginTop: 8 }}>
        {alerts.map((a) => {
          const meta = modeUiMeta(a.mode, state?.modes?.[a.mode]?.mode_label)
          return (
            <div key={a.mode} style={{ fontSize: 12 }} title={`Internal key: ${a.mode}`}>
              <strong style={{ color: 'var(--danger)' }}>{meta.displayName}:</strong> {a.msg}
              <span style={{ marginLeft: 6, opacity: 0.7 }}>({a.mode})</span>
              <button style={{ marginLeft: 8 }} onClick={() => onAck(a.mode)}>Ack</button>
            </div>
          )
        })}
      </div>
    </div>
  )
}

function TableWrap({ children }) {
  return <div className='table-wrap'>{children}</div>
}

function HyperliquidFocusCard({ hyperState, onJumpHyperliquid }) {
  const activeKey = hyperState?.active_strategy_key
  const activeKeys = hyperState?.active_strategy_keys || (activeKey ? [activeKey] : [])
  const focusKey = activeKeys[0] || activeKey || 'hl_15m_trend_follow'
  const focusMeta = modeUiMeta(focusKey, (hyperState?.strategy_registry || {})[focusKey]?.label)
  const latest = hyperState?.latest || {}
  const latestByStrategy = (hyperState?.latest_by_strategy || {})[focusKey] || {}
  const decision = latestByStrategy?.decision?.status || latest?.decision?.status || 'SHADOW_TRACKING'
  const metrics = ((hyperState?.metrics || {}).strategy_overall || {})[focusKey] || {}
  const openPositions = Number(metrics.open_positions ?? 0)
  const netPnl = Number(metrics.net_realized_pnl ?? 0) + Number(metrics.net_unrealized_pnl ?? 0)
  const pnlColor = netPnl > 0 ? 'var(--success)' : netPnl < 0 ? 'var(--danger)' : 'inherit'

  return (
    <div className='panel compact-focus' style={{ marginBottom: 12 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8 }}>
        <strong>Hyperliquid Focus</strong>
        <span className='badge' style={{ fontSize: 11, padding: '4px 8px' }}>{focusMeta.badge || 'ACTIVE LEARNER'}</span>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0, 1fr))', gap: 8, marginTop: 8, fontSize: 12 }}>
        <div title={`Internal key: ${focusMeta.rawKey}`}><strong>Learner</strong><div>{focusMeta.displayName}<div style={{ fontSize: 11, opacity: 0.7 }}>{focusMeta.rawKey}</div></div></div>
        <div><strong>Latest decision</strong><div>{decision}</div></div>
        <div><strong>Net PnL</strong><div style={{ color: pnlColor, fontWeight: 700 }}>{fmt2(netPnl)}</div></div>
        <div><strong>Open positions</strong><div>{openPositions}</div></div>
        <div><strong>Last scan</strong><div>{fmtLA(latest.timestamp)}</div></div>
        <div><strong>Next</strong><div><button onClick={onJumpHyperliquid}>Open Hyperliquid page →</button></div></div>
      </div>
    </div>
  )
}

function HyperliquidResearchSnapshot({ hyperState }) {
  const strategies = Object.entries((hyperState?.metrics || {}).strategy_overall || {})
  if (!strategies.length) return null
  return (
    <div className='panel' style={{ marginBottom: 12 }}>
      <h3 style={{ marginTop: 0 }}>Hyperliquid strategy research snapshot</h3>
      <div style={{ fontSize: 12, opacity: 0.9, marginTop: -4, marginBottom: 8 }}>Quick learner comparison so research is not Kraken-only.</div>
      <TableWrap>
        <table className='rows' style={{ width: '100%' }}>
          <thead>
            <tr><th>Strategy</th><th>Status</th><th>Closed sample</th><th>Expectancy (net)</th><th>Fee drag %</th><th>Net realized</th></tr>
          </thead>
          <tbody>
            {strategies.map(([k, m]) => {
              const meta = modeUiMeta(k, (hyperState?.strategy_registry || {})[k]?.label)
              return (
              <tr key={k}>
                <td title={`Internal key: ${k}`}><div>{meta.displayName}</div><div style={{ fontSize: 11, opacity: 0.7 }}>{k}</div></td>
                <td>{(hyperState?.active_strategy_keys || []).includes(k) ? 'active' : prettyStatus((hyperState?.strategy_registry || {})[k]?.status || 'shadow')}</td>
                <td>{m.sample_closed ?? 0}</td>
                <td>{fmt2(m.expectancy_net ?? 0)}</td>
                <td>{fmt2(m.fee_drag_pct ?? 0)}</td>
                <td>{fmt2(m.net_realized_pnl ?? 0)}</td>
              </tr>
            )})}
          </tbody>
        </table>
      </TableWrap>
    </div>
  )
}

function HyperliquidLogsPanel({ hyperState }) {
  if (!hyperState) return null
  const activeKey = hyperState?.active_strategy_key
  const strategyLatest = (hyperState?.latest_by_strategy || {})[activeKey] || {}
  const activeMeta = modeUiMeta(activeKey, (hyperState?.strategy_registry || {})[activeKey]?.label)
  const positions = (hyperState?.positions || []).slice(-5).reverse()
  const closedTrades = (hyperState?.closed_trades || []).slice(-6).reverse()

  return (
    <div className='panel' style={{ marginBottom: 12 }}>
      <h3 style={{ marginTop: 0 }}>Hyperliquid logs (paper)</h3>
      <div style={{ fontSize: 12 }}>
        <strong>Last scan:</strong> {fmtLA(hyperState?.latest?.timestamp)} | <strong>Strategy:</strong> <span title={`Internal key: ${activeMeta.rawKey}`}>{activeMeta.displayName}</span> <span style={{ opacity: 0.7 }}>({activeMeta.rawKey})</span> | <strong>Decision:</strong> {strategyLatest?.decision?.status || hyperState?.latest?.decision?.status || 'SHADOW_TRACKING'}
      </div>
      <details style={{ marginTop: 8 }}>
        <summary>Recent open position events ({positions.length})</summary>
        <ul style={{ margin: '8px 0 0 18px', fontSize: 12 }}>
          {positions.length ? positions.map((p, i) => (
            <li key={i}>{fmtLA(p.open_time)} · {p.side} · qty {p.qty} · entry {fmt2(p.entry_price)}</li>
          )) : <li>No open position events.</li>}
        </ul>
      </details>
      <details style={{ marginTop: 8 }}>
        <summary>Recent close events ({closedTrades.length})</summary>
        <ul style={{ margin: '8px 0 0 18px', fontSize: 12 }}>
          {closedTrades.length ? closedTrades.map((t, i) => (
            <li key={i}>{fmtLA(t.close_time)} · {t.side || '-'} · net {fmt2(Number(t.net_realized_pnl ?? t.realized_pnl ?? 0))} · {t.close_reason || '-'}</li>
          )) : <li>No close events.</li>}
        </ul>
      </details>
    </div>
  )
}

function HyperliquidPanel({ hstate, strategyKey, onScan, onMockOpen }) {
  if (!hstate) return null
  const latest = hstate.latest || {}
  const market = latest.market || {}
  const candleCount = (latest.candles || []).length
  const risk = hstate.risk_limits || {}
  const fees = hstate.fee_model || {}
  const feeAssumption = hstate.execution_fee_assumption || {}
  const activeStrategyKey = latest.active_strategy_key || hstate.active_strategy_key
  const activeStrategyKeys = latest.active_strategy_keys || hstate.active_strategy_keys || (activeStrategyKey ? [activeStrategyKey] : [])
  const key = strategyKey || activeStrategyKey
  const keyMeta = modeUiMeta(key, (hstate.strategy_registry || {})[key]?.label)
  const strategyLatest = (hstate.latest_by_strategy || {})[key] || {}
  const regime = strategyLatest.regime || latest.regime || {}
  const strategyEntry = (hstate.strategy_registry || {})[key] || {}
  const effectiveStatus = activeStrategyKeys.includes(key) ? 'active / executing' : prettyStatus(strategyEntry.status || 'shadow')
  const metrics = (hstate.metrics || {}).strategy_overall?.[key] || {}
  const book = (hstate.books || {})[key] || {}
  const positions = (book.positions || (hstate.positions || []).filter(p => (p.strategy_key || activeStrategyKey) === key))
  const closedTrades = (book.closed_trades || (hstate.closed_trades || []).filter(t => (t.strategy_key || activeStrategyKey) === key))
  const exposure = positions.reduce((s, p) => s + Number(p.entry_price || 0) * Number(p.qty || 0), 0)
  const marginUsed = positions.reduce((s, p) => s + Number(p.margin_used || 0), 0)
  const freeCollateral = Math.max(0, 1000 - marginUsed)

  const PAPER_START_BALANCE = 1000
  const latestClosed = closedTrades.slice(-1)[0]
  const realizedPnl = closedTrades.reduce((s, t) => s + Number(t.net_realized_pnl ?? t.realized_pnl ?? 0), 0)
  const unrealizedPnl = positions.reduce((s, p) => s + Number(p.unrealized_pnl_net ?? p.unrealized_pnl ?? 0), 0)
  const netPnl = realizedPnl + unrealizedPnl
  const totalFees = closedTrades.reduce((s, t) => s + Number(t.estimated_total_fees ?? t.total_fees ?? 0), 0) + positions.reduce((s, p) => s + Number(p.estimated_total_fees ?? 0), 0)
  const equity = PAPER_START_BALANCE + netPnl

  const pnlColor = (v) => (Number(v) > 0 ? 'var(--success)' : Number(v) < 0 ? 'var(--danger)' : 'inherit')

  return (
    <div className='panel' style={{ marginBottom: 12, borderColor: 'var(--border-strong)' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h3 style={{ margin: 0 }} title={`Internal key: ${keyMeta.rawKey}`}>Hyperliquid Futures Paper Track · {keyMeta.displayName}</h3>
        <span className='badge'>PAPER ONLY · NO LIVE EXECUTION</span>
      </div>
      <div style={{ fontSize: 12, marginTop: 6 }}>
        <strong>Track:</strong> {hstate.track} | <strong>Symbol:</strong> {hstate.symbol} | <strong>Latest:</strong> {fmtLA(latest.timestamp)}
      </div>
      <div style={{ fontSize: 12, marginTop: 4 }}>
        <strong>Market source:</strong> {latest.market_source || 'unknown'} | <strong>Candles loaded:</strong> {candleCount}
      </div>
      <div style={{ fontSize: 12, marginTop: 4 }}>
        <strong>Strategy:</strong> <span title={`Internal key: ${keyMeta.rawKey}`}>{keyMeta.displayName}</span> <span style={{ opacity: 0.7 }}>({keyMeta.rawKey})</span> {activeStrategyKeys.includes(key) ? '(active)' : '(shadow)'} | <strong>Badge:</strong> {keyMeta.badge || '-'} | <strong>Family:</strong> {strategyEntry.family || '-'} | <strong>Status:</strong> {effectiveStatus}
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 8, marginTop: 10, fontSize: 12 }}>
        <div><strong>Leverage (default)</strong><div>{hstate.leverage_default}x</div></div>
        <div><strong>Margin used</strong><div>{fmt2(marginUsed)}</div></div>
        <div><strong>Free collateral*</strong><div>{fmt2(freeCollateral)}</div></div>
        <div><strong>Regime</strong><div>{regime.regime || '-'}</div></div>
        <div><strong>Regime confidence</strong><div>{regime.confidence ?? '-'}</div></div>
        <div><strong>Decision</strong><div>{strategyLatest?.decision?.status || (activeStrategyKeys.includes(key) ? (latest?.decision?.status || '-') : 'SHADOW_TRACKING')}</div></div>
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

      <details style={{ marginTop: 10 }}>
        <summary>Strategy learning snapshot</summary>
        <div style={{ marginTop: 8, fontSize: 12, background: 'var(--cardSoft)', padding: 8, borderRadius: 6, border: '1px solid var(--border)' }}>
          <div>Opened: {metrics.total_opened ?? 0} | Closed: {metrics.total_closed ?? 0} | Open: {metrics.open_positions ?? 0}</div>
          <div>TP / SL / STALE: {metrics.tp_closes ?? 0} / {metrics.sl_closes ?? 0} / {metrics.time_exit_stale_closes ?? 0}</div>
          <div>Net realized: {fmt2(metrics.net_realized_pnl)} | Net unrealized: {fmt2(metrics.net_unrealized_pnl)} | Fees: {fmt2(metrics.total_fees)} | Fee drag: {fmt2(metrics.fee_drag_pct)}%</div>
          <div>Expectancy (net): {fmt2(metrics.expectancy_net)} | Median time-to-close: {metrics.median_time_to_close_min ?? 0} min</div>
        </div>
      </details>

      <details style={{ marginTop: 10 }}>
        <summary>Latest closed trade</summary>
        <div style={{ marginTop: 8, fontSize: 12, background: 'var(--cardSoft)', padding: 8, borderRadius: 6, border: '1px solid var(--border)' }}>
          {latestClosed ? (
            <div style={{ marginTop: 6 }}>
              <div>Close: {fmtLA(latestClosed.close_time)} | Reason: {latestClosed.close_reason || '-'} | Leverage: {latestClosed.leverage ? `${latestClosed.leverage}x` : '-'}</div>
              <div>Entry/Close: {fmt2(Number(latestClosed.entry_price ?? latestClosed.entry_fill_price ?? 0))} / {fmt2(Number(latestClosed.close_price ?? latestClosed.close_fill_price ?? 0))} | Net PnL: <strong style={{ color: pnlColor(Number(latestClosed.net_realized_pnl ?? latestClosed.realized_pnl ?? 0)) }}>{fmt2(Number(latestClosed.net_realized_pnl ?? latestClosed.realized_pnl ?? 0))}</strong></div>
            </div>
          ) : <div style={{ marginTop: 6 }}>No closed trades yet.</div>}
        </div>
      </details>

      <details style={{ marginTop: 10 }}>
        <summary>Paper account summary (simulator baseline)</summary>
        <div style={{ marginTop: 8, fontSize: 12, background: 'var(--cardSoft)', padding: 8, borderRadius: 6, border: '1px solid var(--border)' }}>
          <div style={{ display:'grid', gridTemplateColumns:'repeat(3, 1fr)', gap:8, marginTop:6 }}>
            <div><strong>Starting balance</strong><div>{fmt2(PAPER_START_BALANCE)}</div></div>
            <div><strong>Realized PnL</strong><div style={{ color: pnlColor(realizedPnl) }}>{fmt2(realizedPnl)}</div></div>
            <div><strong>Unrealized PnL</strong><div style={{ color: pnlColor(unrealizedPnl) }}>{fmt2(unrealizedPnl)}</div></div>
            <div><strong>Net PnL</strong><div style={{ color: pnlColor(netPnl) }}>{fmt2(netPnl)}</div></div>
            <div><strong>Total fees</strong><div>{fmt2(totalFees)}</div></div>
            <div><strong>Current equity</strong><div style={{ color: pnlColor(netPnl) }}>{fmt2(equity)}</div></div>
          </div>
        </div>
      </details>

      {activeStrategyKeys.includes(key) && (
        <div style={{ marginTop: 10 }}>
          <button onClick={onScan}>Run Hyperliquid Mock Scan</button>
          <button style={{ marginLeft: 8 }} onClick={onMockOpen}>Mock Open Paper Position</button>
        </div>
      )}

      <details style={{ marginTop: 10 }}>
        <summary>Open futures paper trades ({positions.length})</summary>
        <TableWrap>
          <table className='rows' style={{ width: '100%' }}>
            <thead>
              <tr>
                <th>Symbol</th><th>Side</th><th>Entry time</th><th>Entry price</th><th>Qty</th><th>Entry notional</th><th>Leverage</th><th>Current price</th><th>Unrealized PnL (net)</th><th>Current return %</th><th>TP</th><th>SL</th>
              </tr>
            </thead>
            <tbody>
              {positions.slice(-10).map((p, i) => {
                const entryPrice = Number(p.entry_price ?? 0)
                const qty = Number(p.qty ?? 0)
                const entryNotional = Number(p.entry_notional ?? (entryPrice * qty))
                const currentPrice = Number(market.mark_price ?? market.price ?? latest.price ?? 0)
                const unrl = Number(p.unrealized_pnl_net ?? p.unrealized_pnl ?? 0)
                const retPct = entryNotional > 0 ? (unrl / entryNotional) * 100 : null
                return (
                  <tr key={i}>
                    <td>{hstate.symbol || '-'}</td>
                    <td>{p.side}</td>
                    <td>{fmtLA(p.open_time)}</td>
                    <td>{fmt2(entryPrice)}</td>
                    <td>{p.qty}</td>
                    <td>{fmt2(entryNotional)}</td>
                    <td>{p.leverage}x</td>
                    <td>{fmt2(currentPrice)}</td>
                    <td style={{ color: pnlColor(unrl), fontWeight: 700 }}>{fmt2(unrl)}</td>
                    <td style={{ color: pnlColor(retPct ?? 0) }}>{retPct == null ? '-' : `${fmt2(retPct)}%`}</td>
                    <td>{p.take_profit ?? latest?.decision?.take_profit ?? '-'}</td>
                    <td>{p.stop_loss ?? latest?.decision?.stop_loss ?? '-'}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </TableWrap>
      </details>

      <details style={{ marginTop: 10 }}>
        <summary>Closed futures trades ({closedTrades.length})</summary>
        <TableWrap>
          <table className='rows' style={{ width: '100%' }}>
            <thead>
              <tr>
                <th>Symbol</th><th>Side</th><th>Entry time</th><th>Close time</th><th>Entry price</th><th>Close price</th><th>Qty</th><th>Leverage</th><th>Entry notional</th><th>Margin used</th><th>Gross PnL</th><th>Fees</th><th>Net PnL</th><th>Return %</th><th>Close reason</th><th>Strategy</th><th>Regime</th>
              </tr>
            </thead>
            <tbody>
              {closedTrades.slice(-12).reverse().map((t, i) => {
                const gross = Number(t.gross_realized_pnl ?? 0)
                const feesPaid = Number(t.estimated_total_fees ?? t.total_fees ?? 0)
                const net = Number(t.net_realized_pnl ?? t.realized_pnl ?? 0)
                const entryPrice = Number(t.entry_price ?? t.entry_fill_price ?? 0)
                const qty = Number(t.qty ?? 0)
                const entryNotional = Number(t.entry_notional ?? (entryPrice * qty))
                const marginUsed = Number(t.margin_used ?? (t.leverage ? entryNotional / Number(t.leverage) : 0))
                const retPct = entryNotional > 0 ? (net / entryNotional) * 100 : null
                return (
                  <tr key={i}>
                    <td>{hstate.symbol || '-'}</td>
                    <td>{t.side || '-'}</td>
                    <td>{fmtLA(t.open_time || t.entry_time)}</td>
                    <td>{fmtLA(t.close_time)}</td>
                    <td>{fmt2(entryPrice)}</td>
                    <td>{fmt2(Number(t.close_price ?? t.close_fill_price ?? 0))}</td>
                    <td>{t.qty ?? '-'}</td>
                    <td>{t.leverage ? `${t.leverage}x` : '-'}</td>
                    <td>{fmt2(entryNotional)}</td>
                    <td>{marginUsed > 0 ? fmt2(marginUsed) : '-'}</td>
                    <td style={{ color: pnlColor(gross) }}>{fmt2(gross)}</td>
                    <td>{fmt2(feesPaid)}</td>
                    <td style={{ color: pnlColor(net), fontWeight: 700 }}>{fmt2(net)}</td>
                    <td style={{ color: pnlColor(retPct ?? 0) }}>{retPct == null ? '-' : `${fmt2(retPct)}%`}</td>
                    <td>{t.close_reason || '-'}</td>
                    <td>{(() => { const raw = t.strategy_key || hstate.active_strategy_key || '-'; const meta = modeUiMeta(raw, (hstate.strategy_registry || {})[raw]?.label); return <span title={`Internal key: ${raw}`}>{meta.displayName}<span style={{ opacity: 0.7 }}> ({raw})</span></span> })()}</td>
                    <td>{t.regime_label || t.market_regime || latest?.regime?.regime || '-'}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </TableWrap>
      </details>

      <div style={{ fontSize: 11, opacity: 0.75, marginTop: 6 }}>*Free collateral is a simulator placeholder estimate for paper training view.</div>
    </div>
  )
}

function ModePanel({ modeKey, m, onAck, showEvaluation = true, showTradeDetails = true, showLogs = true }) {
  const d = m?.latest_decision || {}
  const uiMeta = modeUiMeta(modeKey, m?.mode_label)
  const modeRole = modeKey === 'btc_15m_conservative' ? 'baseline/reference' : 'autonomous learner'
  const isBaselineMode = modeKey === 'btc_15m_conservative'
  const comparatorVerdict = m?.comparator_verdict || m?.comparison_vs_baseline?.verdict || '-'
  const modeReview = m?.mode_review_recommendation?.recommended_status || '-'
  const policy = m?.mode_regime_policy_summary || {}
  const policyConfidence = policy?.policy_confidence || '-'
  const preferredRegimes = Array.isArray(policy?.preferred_regimes) ? policy.preferred_regimes : []
  const cautionRegimes = Array.isArray(policy?.caution_regimes) ? policy.caution_regimes : []
  const avoidRegimes = Array.isArray(policy?.avoid_regimes) ? policy.avoid_regimes : []
  const inconclusiveRegimes = Array.isArray(policy?.inconclusive_regimes) ? policy.inconclusive_regimes : []
  const formatRegimes = (arr) => (arr.length ? arr.join(', ') : '-')
  const openPos = (m?.open_positions || [])[0]
  const latestClosed = (m?.closed_trades || []).slice(-1)[0]
  const tradeAge = openPos?.open_time ? Math.max(0, Math.floor((Date.now() - new Date(openPos.open_time).getTime()) / 60000)) : null
  const bid = m?.market_data?.[0]?.bid ?? 0
  const ask = m?.market_data?.[0]?.ask ?? 0
  const spreadPct = m?.market_data?.[0]?.spread_pct ?? 0
  const realized = m?.current_pnl?.realized ?? 0
  const unrealized = m?.current_pnl?.unrealized ?? 0
  const feeDragPct = m?.current_pnl?.fee_drag_pct_of_gross_pnl ?? m?.mode_stats?.fee_drag_pct_of_gross_pnl ?? 0
  const allHistory = m?.history || []
  const lifecycleRows = allHistory.filter(r => ['PAPER_TRADE_OPEN', 'PAPER_TRADE_CLOSED'].includes(r?.status))
  const diagRows = allHistory.filter(r => ['WAIT', 'REJECT'].includes(r?.status))
  const closedTrades = m?.closed_trades || []
  const expectancy = m?.mode_stats?.expectancy ?? m?.strategy_metrics?.expectancy ?? 0
  const diagCounts = diagRows.reduce((acc, r) => {
    const key = `${r?.status || 'UNKNOWN'}|${r?.reason || r?.regime_label || 'n/a'}`
    acc[key] = (acc[key] || 0) + 1
    return acc
  }, {})
  const diagTop = Object.entries(diagCounts).sort((a, b) => b[1] - a[1]).slice(0, 5)
  const pnlColor = (v) => (Number(v) > 0 ? 'var(--success)' : Number(v) < 0 ? 'var(--danger)' : 'inherit')

  return (
    <div className='panel' style={{ marginBottom: 12 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <h3 title={`Internal key: ${uiMeta.rawKey}`} style={{ margin: 0 }}>{uiMeta.displayName}</h3>
        {uiMeta.badge && <span className='badge'>{uiMeta.badge}</span>}
      </div>
      <div style={{ fontSize: 12, opacity: .7, marginTop: 4, marginBottom: 2 }}>Internal key: {uiMeta.rawKey}</div>
      <div style={{ fontSize: 12, opacity: .8, marginTop: -2, marginBottom: 6 }}>Role: <strong>{modeRole}</strong></div>
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

      <div style={{ marginTop: 8, fontSize: 12, background: 'var(--cardSoft)', padding: 8, borderRadius: 6, border: '1px solid var(--border)' }}>
        <strong>Quick summary</strong>
        <div style={{ display:'grid', gridTemplateColumns:'repeat(4, 1fr)', gap:8, marginTop:6 }}>
          <div><strong>Open / Closed</strong><div>{(m?.open_positions || []).length} / {(m?.closed_trades || []).length}</div></div>
          <div><strong>Sample</strong><div>{m?.strategy_metrics?.sample_size ?? 0}</div></div>
          <div><strong>Net realized</strong><div style={{ color: pnlColor(realized) }}>{fmt2(realized)}</div></div>
          <div><strong>Net unrealized</strong><div style={{ color: pnlColor(unrealized) }}>{fmt2(unrealized)}</div></div>
          <div><strong>Expectancy</strong><div style={{ color: pnlColor(expectancy) }}>{fmt2(expectancy)}</div></div>
          <div><strong>Fee drag %</strong><div>{fmt2(feeDragPct)}%</div></div>
          <div><strong>Bid / Ask</strong><div>{bid} / {ask}</div></div>
          <div><strong>Spread %</strong><div>{Number(spreadPct).toFixed(6)}%</div></div>
        </div>
      </div>

      {showEvaluation && (
        <div style={{ marginTop: 8, fontSize: 12, background: 'var(--cardSoft)', padding: 8, borderRadius: 6, border: '1px solid var(--border)' }}>
          <strong>Evaluation summary</strong>
          {isBaselineMode ? (
            <div style={{ marginTop: 6, opacity: 0.85 }}>Baseline reference mode (comparator target).</div>
          ) : (
            <div style={{ marginTop: 6, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
              <div><strong>Comparator verdict</strong><div>{comparatorVerdict}</div></div>
              <div><strong>Mode review</strong><div>{modeReview}</div></div>
              <div><strong>Policy confidence</strong><div>{policyConfidence}</div></div>
              <div><strong>Preferred regimes</strong><div>{formatRegimes(preferredRegimes)}</div></div>
              <div><strong>Caution regimes</strong><div>{formatRegimes(cautionRegimes)}</div></div>
              <div><strong>Avoid regimes</strong><div>{formatRegimes(avoidRegimes)}</div></div>
              <div style={{ gridColumn: '1 / span 2' }}><strong>Inconclusive regimes</strong><div>{formatRegimes(inconclusiveRegimes)}</div></div>
            </div>
          )}
        </div>
      )}

      {showTradeDetails && (
        <>
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
            <summary>Open Kraken paper trades ({(m?.open_positions || []).length})</summary>
            <TableWrap>
              <table className='rows' style={{ width: '100%' }}>
                <thead><tr><th>Symbol</th><th>Side</th><th>Entry time</th><th>Entry price</th><th>Qty</th><th>Entry notional</th><th>Current price</th><th>Unrealized PnL (net)</th><th>Current return %</th><th>TP</th><th>SL</th></tr></thead>
                <tbody>
                  {(m?.open_positions || []).slice(-10).map((p, i) => {
                    const entryPrice = Number(p.entry_fill_price ?? p.entry_price ?? 0)
                    const qty = Number(p.qty ?? 0)
                    const entryNotional = Number(p.entry_notional ?? (entryPrice * qty))
                    const currentPrice = Number(m?.market_data?.[0]?.ohlcv?.slice(-1)[0]?.close ?? m?.market_data?.[0]?.bid ?? 0)
                    const unrl = Number(p.net_unrealized_pnl ?? p.unrealized_pnl ?? 0)
                    const retPct = entryNotional > 0 ? (unrl / entryNotional) * 100 : null
                    return (
                      <tr key={i}>
                        <td>BTC/USD</td><td>{p.side}</td><td>{fmtLA(p.open_time)}</td><td>{fmt2(entryPrice)}</td><td>{p.qty}</td><td>{fmt2(entryNotional)}</td><td>{fmt2(currentPrice)}</td>
                        <td style={{ color: pnlColor(unrl), fontWeight: 700 }}>{fmt2(unrl)}</td>
                        <td style={{ color: pnlColor(retPct ?? 0) }}>{retPct == null ? '-' : `${fmt2(retPct)}%`}</td>
                        <td>{p.take_profit ?? '-'}</td><td>{p.stop_loss ?? '-'}</td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </TableWrap>
          </details>

          <details style={{ marginTop: 6 }}>
            <summary>Closed Kraken paper trades ({closedTrades.length})</summary>
            <TableWrap>
              <table className='rows' style={{ width: '100%' }}>
                <thead><tr><th>Symbol</th><th>Side</th><th>Entry time</th><th>Close time</th><th>Entry price</th><th>Close price</th><th>Qty</th><th>Entry notional</th><th>Gross PnL</th><th>Fees</th><th>Net PnL</th><th>Return %</th><th>Close reason</th><th>Strategy</th><th>Regime</th></tr></thead>
                <tbody>
                  {closedTrades.slice(-12).reverse().map((t, i) => {
                    const gross = Number(t.gross_realized_pnl ?? 0)
                    const feesPaid = Number(t.total_fees ?? t.estimated_total_fees ?? ((t.entry_fee ?? 0) + (t.close_fee ?? 0)))
                    const net = Number(t.net_realized_pnl ?? t.realized_pnl ?? 0)
                    const entryNotional = Number(t.entry_notional ?? (Number(t.entry_fill_price ?? 0) * Number(t.qty ?? 0)))
                    const retPct = entryNotional > 0 ? (net / entryNotional) * 100 : null
                    return (
                      <tr key={i}>
                        <td>BTC/USD</td><td>{t.side || '-'}</td><td>{fmtLA(t.open_time || t.entry_time)}</td><td>{fmtLA(t.close_time)}</td><td>{fmt2(Number(t.entry_fill_price ?? t.entry_price ?? 0))}</td><td>{fmt2(Number(t.close_fill_price ?? t.close_price ?? 0))}</td>
                        <td>{t.qty ?? '-'}</td><td>{fmt2(entryNotional)}</td><td style={{ color: pnlColor(gross) }}>{fmt2(gross)}</td><td>{fmt2(feesPaid)}</td><td style={{ color: pnlColor(net), fontWeight: 700 }}>{fmt2(net)}</td>
                        <td style={{ color: pnlColor(retPct ?? 0) }}>{retPct == null ? '-' : `${fmt2(retPct)}%`}</td><td>{t.close_reason || '-'}</td><td>{(() => { const raw = t.strategy_key || m?.mode || modeKey; const meta = modeUiMeta(raw, m?.mode_label); return <span title={`Internal key: ${raw}`}>{meta.displayName}<span style={{ opacity: 0.7 }}> ({raw})</span></span> })()}</td><td>{t.regime_label || t.market_regime || m?.current_regime?.regime || '-'}</td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </TableWrap>
          </details>
        </>
      )}

      {showLogs && (
        <>
          <details style={{ marginTop: 6 }}>
            <summary>Recent lifecycle history ({lifecycleRows.length})</summary>
            <TableWrap>
              <table className='rows' style={{ width: '100%' }}>
                <thead><tr><th>Time</th><th>Status</th><th>Regime</th><th>R:R</th></tr></thead>
                <tbody>
                  {lifecycleRows.slice(-8).reverse().map((r, i) => (
                    <tr key={i}><td>{fmtLA(r.timestamp)}</td><td>{r.status}</td><td>{r.regime_label}</td><td>{r.risk_reward_ratio}</td></tr>
                  ))}
                </tbody>
              </table>
            </TableWrap>
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
        </>
      )}
    </div>
  )
}

export default function App() {
  const [state, setState] = useState(null)
  const [hyperState, setHyperState] = useState(null)
  const [newsState, setNewsState] = useState(null)
  const [err, setErr] = useState('')
  const [theme, setTheme] = useState('dark')
  const [activePage, setActivePage] = useState('Overview')

  const load = async () => {
    try {
      const s = await fetch(`${API}/api/state`).then(r => r.json())
      const h = await fetch(`${API}/api/history`).then(r => r.json())
      const hs = await fetch(`${API}/api/hyperliquid/state`).then(r => r.json())
      const ns = await fetch(`${API}/api/news/context`).then(r => r.json())
      if (h?.history && typeof h.history === 'object') {
        for (const k of Object.keys(h.history)) {
          if (s?.modes?.[k]) s.modes[k].history = h.history[k]
        }
      }
      setState(s)
      setHyperState(hs)
      setNewsState(ns)
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

  const rows = []
  for (const k of MODE_ORDER) {
    const m = state?.modes?.[k]
    if (!m) continue
    const perf = m?.performance_by_regime || {}
    const sortedRegimes = Object.entries(perf).sort((a, b) => (b?.[1]?.expectancy ?? -9999) - (a?.[1]?.expectancy ?? -9999))
    const best = sortedRegimes[0]?.[0]
    const bestSample = sortedRegimes[0]?.[1]?.sample_size || 0
    const expectancy = Number(m?.strategy_metrics?.expectancy ?? 0)
    const feeDrag = Number(m?.strategy_metrics?.fee_drag_pct ?? 0)
    const scoreMeta = scoreMetaForMode(m)
    const uiMeta = modeUiMeta(k, m?.mode_label)
    rows.push({
      key: k,
      displayName: uiMeta.displayName,
      badge: uiMeta.badge,
      family: m?.strategy_registry_entry?.family || '-',
      symbol: 'BTC/USD',
      status: prettyStatus(m?.strategy_status),
      bestRegime: best,
      expectancy,
      feeDrag,
      netRealized: Number(m?.strategy_metrics?.realized_pnl ?? 0),
      score: scoreMeta.numeric,
      closed: Number(m?.strategy_metrics?.closed_trades ?? 0),
      confidence: strategyConfidence({ closed: Number(m?.strategy_metrics?.closed_trades ?? 0), bestRegimeSample: bestSample, expectancy, feeDrag }),
    })
  }

  const hKey = hyperState?.active_strategy_key
  const hActiveKeys = hyperState?.active_strategy_keys || (hKey ? [hKey] : [])
  const hOverall = (hyperState?.metrics || {}).strategy_overall || {}
  const hRegistry = hyperState?.strategy_registry || {}
  const hKeys = ['hl_15m_trend_follow', 'hl_15m_trend_follow_momo_gate_v1'].filter(k => hRegistry[k] || hOverall[k])
  for (const sk of hKeys) {
    const hm = hOverall?.[sk] || {}
    const byReg = (hyperState?.metrics || {}).strategy_regime || {}
    const regimeRows = Object.entries(byReg)
      .filter(([rk]) => rk.startsWith(`${sk}|`))
      .map(([rk, v]) => ({ regime: rk.split('|')[1], ex: Number(v?.expectancy_net ?? 0), sample: Number(v?.sample_closed ?? 0) }))
      .sort((a, b) => b.ex - a.ex)
    const best = regimeRows[0]
    const expectancy = Number(hm.expectancy_net ?? 0)
    const feeDrag = Number(hm.fee_drag_pct ?? 0)
    const score = 50 + (expectancy * 120) - (feeDrag * 0.2) + (best?.ex > 0 ? 8 : -8)
    const status = hActiveKeys.includes(sk) ? 'active' : prettyStatus(hRegistry?.[sk]?.status || 'shadow')
    const uiMeta = modeUiMeta(sk, hRegistry?.[sk]?.label)
    rows.push({
      key: sk,
      displayName: uiMeta.displayName,
      badge: uiMeta.badge,
      family: hRegistry?.[sk]?.family || 'trend_follow',
      symbol: hyperState?.symbol || 'ETH-PERP',
      status,
      bestRegime: best?.regime || '-',
      expectancy,
      feeDrag,
      netRealized: Number(hm.net_realized_pnl ?? 0),
      score,
      closed: Number(hm.sample_closed ?? 0),
      confidence: strategyConfidence({ closed: Number(hm.sample_closed ?? 0), bestRegimeSample: Number(best?.sample ?? 0), expectancy, feeDrag }),
    })
  }

  rows.sort((a, b) => (b.expectancy - a.expectancy) || (a.feeDrag - b.feeDrag))
  const primaryHlKeys = ['hl_15m_trend_follow', 'hl_15m_trend_follow_momo_gate_v1']
  const hlPanelKeys = primaryHlKeys.filter(k => (hyperState?.strategy_registry || {})[k])

  const renderPage = () => {
    if (activePage === 'Overview') {
      return (
        <>
          <HyperliquidFocusCard hyperState={hyperState} onJumpHyperliquid={() => setActivePage('Hyperliquid')} />
          <RuntimePanel state={state} />
          <AlertStrip state={state} onAck={ack} />
          <NewsPanel news={newsState} compact />
          <ScoreboardTable rows={rows} />
          <SharedChart state={state} theme={theme} compact />
        </>
      )
    }

    if (activePage === 'Hyperliquid') {
      return (
        <>
          <div className='panel' style={{ marginBottom: 8 }}><strong>Hyperliquid Track</strong> <span className='badge'>reference + autonomous learner</span></div>
          {hlPanelKeys.map((k) => (
            <HyperliquidPanel key={k} hstate={hyperState} strategyKey={k} onScan={runHyperScan} onMockOpen={mockHyperOpen} />
          ))}
        </>
      )
    }

    if (activePage === 'Kraken') {
      return (
        <div className='grid' style={{ gridTemplateColumns: '1fr 1fr' }}>
          {MODE_ORDER.map(k => <ModePanel key={k} modeKey={k} m={state?.modes?.[k]} onAck={ack} showEvaluation={false} showTradeDetails showLogs={false} />)}
        </div>
      )
    }

    if (activePage === 'Research') {
      return (
        <>
          <HyperliquidResearchSnapshot hyperState={hyperState} />
          <div className='grid' style={{ gridTemplateColumns: '1fr 1fr' }}>
            {MODE_ORDER.map(k => <ModePanel key={k} modeKey={k} m={state?.modes?.[k]} onAck={ack} showEvaluation showTradeDetails={false} showLogs={false} />)}
          </div>
        </>
      )
    }

    return (
      <>
        <NewsPanel news={newsState} />
        <HyperliquidLogsPanel hyperState={hyperState} />
        <div className='grid' style={{ gridTemplateColumns: '1fr 1fr' }}>
          {MODE_ORDER.map(k => <ModePanel key={k} modeKey={k} m={state?.modes?.[k]} onAck={ack} showEvaluation={false} showTradeDetails={false} showLogs />)}
        </div>
      </>
    )
  }

  return (
    <div className={`wrap theme-${theme}`}>
      <div className='top'>
        <h2>Paper Trading Dashboard · Kraken (Baseline + Learner) · Hyperliquid (Reference + Learner)</h2>
        <div style={{ display: 'flex', gap: 8 }}>
          <span className='badge'>PAPER MODE</span>
          <button onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}>{theme === 'dark' ? 'Light' : 'Dark'}</button>
          <button onClick={runScanBoth}>Run Both Scans</button>
          <button onClick={toggleAuto}>{state.auto_scan ? 'Pause Auto' : 'Resume Auto'}</button>
        </div>
      </div>

      <div className='app-shell'>
        <aside className='panel side-nav'>
          {PAGES.map((page) => (
            <button key={page} className={`nav-btn ${activePage === page ? 'active' : ''}`} onClick={() => setActivePage(page)}>{page}</button>
          ))}
        </aside>

        <main>
          <div className='page-head'>
            <h3 style={{ margin: 0 }}>{activePage}</h3>
            <div className='page-subtitle'>{PAGE_SUBTITLES[activePage]}</div>
          </div>
          {err && <div className='panel' style={{ color: 'var(--danger)', borderColor: 'var(--danger)' }}>{err}</div>}
          {renderPage()}
        </main>
      </div>
    </div>
  )
}
