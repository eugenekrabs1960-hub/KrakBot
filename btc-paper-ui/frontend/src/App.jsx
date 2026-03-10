import React, { useEffect, useMemo, useRef, useState } from 'react'
import { createChart } from 'lightweight-charts'

const API = 'http://127.0.0.1:8000'

function Chart({ candles, upper, lower }) {
  const ref = useRef(null)
  useEffect(() => {
    if (!ref.current || !candles?.length) return
    ref.current.innerHTML = ''
    const chart = createChart(ref.current, { height: 360, layout: { background: { color: '#161b22' }, textColor: '#e6edf3' } })
    const series = chart.addCandlestickSeries()
    series.setData(candles.map(c => ({
      time: Math.floor(new Date(c.time).getTime() / 1000), open: c.open, high: c.high, low: c.low, close: c.close
    })))
    series.createPriceLine({ price: upper, color: '#f85149', lineStyle: 2, lineWidth: 1, title: '69513.0' })
    series.createPriceLine({ price: lower, color: '#2ea043', lineStyle: 2, lineWidth: 1, title: '68698.6' })
    chart.timeScale().fitContent()
    return () => chart.remove()
  }, [candles, upper, lower])
  return <div ref={ref} />
}

export default function App() {
  const [state, setState] = useState(null)
  const [history, setHistory] = useState([])
  const [uiError, setUiError] = useState('')

  const load = async () => {
    try {
      const s = await fetch(`${API}/api/state`).then(r => r.json())
      const h = await fetch(`${API}/api/history`).then(r => r.json())
      setState(s)
      setHistory(h.history || [])
      setUiError('')
    } catch (e) {
      setUiError('Failed to load dashboard state.')
    }
  }

  const runScan = async () => {
    await fetch(`${API}/api/run-scan`, { method: 'POST' })
    await load()
  }

  const setMode = async (mode) => {
    try {
      const res = await fetch(`${API}/api/mode/${mode}`, { method: 'POST' })
      const data = await res.json()
      if (!res.ok || !data.ok) {
        throw new Error(data?.message || 'Mode switch failed')
      }
      if (data.state) {
        setState(data.state)
      }
      const h = await fetch(`${API}/api/history`).then(r => r.json())
      setHistory(h.history || [])
      setUiError('')
    } catch (e) {
      setUiError(`Mode switch failed: ${e.message}`)
    }
  }

  const toggle = async () => {
    await fetch(`${API}/api/auto-scan`, { method: 'POST' })
    await load()
  }

  const ackNotify = async () => {
    await fetch(`${API}/api/ack-notify`, { method: 'POST' })
    await load()
  }

  useEffect(() => {
    load()
    const t = setInterval(load, 15000)
    return () => clearInterval(t)
  }, [])

  const md = useMemo(() => state?.market_data?.[0] || null, [state])
  const d = state?.latest_decision || {}
  const statusColor = d.status === 'WAIT' ? '#2ea043' : d.status === 'REJECT' ? '#d29922' : d.status === 'PROPOSE_TRADE' ? '#f85149' : d.status?.includes('OPEN') ? '#1f6feb' : '#8b949e'

  if (!state || !md) return <div className='wrap'>Loading...</div>

  return <div className='wrap'>
    {uiError && (
      <div className='panel' style={{borderColor:'#f85149', marginBottom:12, color:'#f85149'}}>{uiError}</div>
    )}
    {state.notify_user && (
      <div className='panel' style={{borderColor:'#f85149', marginBottom:12}}>
        <strong style={{color:'#f85149'}}>{state.notify_user.message}</strong>
        <p style={{margin:'6px 0',fontSize:12}}>{state.notify_user?.decision?.reason}</p>
        <button onClick={ackNotify}>Acknowledge</button>
      </div>
    )}

    <div className='top'>
      <div>
        <h2>BTC/USD Paper Dashboard</h2>
        <div style={{fontSize:12,opacity:.8}}>
          Mode: {state.mode_label || state.active_mode} | Market update: {state.latest_market_data_time || '-'} | Scan: {state.latest_scan_time || '-'} | Decision: {state.latest_decision_time || '-'}
        </div>
      </div>
      <div style={{display:'flex',gap:8,alignItems:'center'}}>
        <span className='badge'>PAPER MODE</span>
        <span style={{background:statusColor,color:'#fff',padding:'6px 10px',borderRadius:999,fontWeight:700,fontSize:12}}>
          AUTO: {d.status || 'INSUFFICIENT_DATA'}
        </span>
        <span style={{fontSize:12,opacity:.85}}>at {state.latest_decision_time || '-'}</span>
        <button style={{background:state.active_mode==='btc_15m_conservative'?'#1f6feb':'', color:state.active_mode==='btc_15m_conservative'?'#fff':''}} onClick={() => setMode('btc_15m_conservative')}>BTC/USD 15m conservative</button>
        <button style={{background:state.active_mode==='btc_5m_aggressive'?'#1f6feb':'', color:state.active_mode==='btc_5m_aggressive'?'#fff':''}} onClick={() => setMode('btc_5m_aggressive')}>BTC/USD 5m aggressive</button>
        <button onClick={runScan}>Run Scan</button>
        <button onClick={toggle}>{state.auto_scan ? 'Pause Auto Scan' : 'Resume Auto Scan'}</button>
      </div>
    </div>

    <div className='grid'>
      <div className='panel'>
        <Chart candles={md.ohlcv} upper={state.triggers.upper} lower={state.triggers.lower} />
      </div>
      <div className='panel'>
        <h3>Latest Decision</h3>
        <p>Status: <strong style={{color:d.status==='PROPOSE_TRADE'?'#f85149':'#e6edf3'}}>{d.status}</strong></p>
        <p>Regime: {d.regime_label}</p>
        <p>Side: {d.side || '-'}</p>
        <p>Entry: {d.entry_price || 0}</p>
        <p>Stop Loss: {d.stop_loss || 0}</p>
        <p>Take Profit: {d.take_profit || 0}</p>
        <p>Invalidation: {d.invalidation || '-'}</p>
        <p>R:R: {d.risk_reward_ratio}</p>
        <p style={{fontSize:12}}>Reason: {d.reason}</p>
        <hr />
        <h3>Account</h3>
        <p>Equity: {state.account_state.account_equity}</p>
        <p>Cash: {state.account_state.cash_available}</p>
        <p>Bid/Ask: {md.bid} / {md.ask}</p>
        <p>Spread: {md.spread} ({md.spread_pct.toFixed(6)}%)</p>
        <p>PnL Unrealized: {state.current_pnl?.unrealized ?? 0}</p>
        <p>PnL Realized: {state.current_pnl?.realized ?? 0}</p>
      </div>
    </div>

    <div className='panel' style={{marginTop:12}}>
      <h3>Pending Paper Orders</h3>
      <table className='rows' style={{width:'100%'}}>
        <thead><tr><th>Time</th><th>Signal</th><th>Status</th></tr></thead>
        <tbody>
          {(state.pending_orders || []).slice().reverse().map((o,i)=><tr key={i}><td>{o.timestamp}</td><td>{o.signal_id}</td><td>{o.status}</td></tr>)}
        </tbody>
      </table>
    </div>

    <div className='panel' style={{marginTop:12}}>
      <h3>Open Paper Positions</h3>
      <table className='rows' style={{width:'100%'}}>
        <thead><tr><th>Open</th><th>Side</th><th>Entry</th><th>SL</th><th>TP</th><th>Unrealized PnL</th></tr></thead>
        <tbody>
          {(state.open_positions || []).map((p,i)=><tr key={i}><td>{p.open_time}</td><td>{p.side}</td><td>{p.entry_fill_price}</td><td>{p.stop_loss}</td><td>{p.take_profit}</td><td>{p.unrealized_pnl}</td></tr>)}
        </tbody>
      </table>
    </div>

    <div className='panel' style={{marginTop:12}}>
      <h3>Closed Paper Trades</h3>
      <table className='rows' style={{width:'100%'}}>
        <thead><tr><th>Open</th><th>Close</th><th>Side</th><th>Entry</th><th>ClosePx</th><th>Realized PnL</th><th>Reason</th></tr></thead>
        <tbody>
          {(state.closed_trades || []).slice().reverse().map((t,i)=><tr key={i}><td>{t.open_time}</td><td>{t.close_time}</td><td>{t.side}</td><td>{t.entry_fill_price}</td><td>{t.close_fill_price}</td><td>{t.realized_pnl}</td><td>{t.close_reason}</td></tr>)}
        </tbody>
      </table>
    </div>

    <div className='panel' style={{marginTop:12}}>
      <h3>Mode Stats</h3>
      <p>Total Opened: {state.mode_stats?.total_opened ?? 0} | Total Closed: {state.mode_stats?.total_closed ?? 0}</p>
      <p>Win Rate: {state.mode_stats?.win_rate ?? 0}% | Avg Win: {state.mode_stats?.average_win ?? 0} | Avg Loss: {state.mode_stats?.average_loss ?? 0}</p>
      <p>Realized: {state.mode_stats?.realized_pnl ?? 0} | Unrealized: {state.mode_stats?.unrealized_pnl ?? 0} | Max Drawdown: {state.mode_stats?.max_drawdown ?? 0}</p>
      <pre style={{whiteSpace:'pre-wrap',fontSize:11}}>{JSON.stringify(state.mode_stats?.performance_by_regime || {}, null, 2)}</pre>
    </div>

    <div className='panel' style={{marginTop:12}}>
      <h3>Recent Scan / Decision History</h3>
      <table className='rows' style={{width:'100%'}}>
        <thead><tr><th>Scan Time</th><th>Decision Time</th><th>Status</th><th>Side</th><th>Entry</th><th>SL</th><th>TP</th><th>Regime</th><th>R:R</th></tr></thead>
        <tbody>
          {history.slice().reverse().map((r,i)=><tr key={i}><td>{r.timestamp}</td><td>{r.decision_time || '-'}</td><td>{r.status}</td><td>{r.side || '-'}</td><td>{r.entry_price || 0}</td><td>{r.stop_loss || 0}</td><td>{r.take_profit || 0}</td><td>{r.regime_label}</td><td>{r.risk_reward_ratio}</td></tr>)}
        </tbody>
      </table>
    </div>
  </div>
}
