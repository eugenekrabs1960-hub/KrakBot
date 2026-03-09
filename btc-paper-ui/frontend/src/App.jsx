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

  const load = async () => {
    const s = await fetch(`${API}/api/state`).then(r => r.json())
    const h = await fetch(`${API}/api/history`).then(r => r.json())
    setState(s)
    setHistory(h.history || [])
  }

  const runScan = async () => {
    await fetch(`${API}/api/run-scan`, { method: 'POST' })
    await load()
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
  const statusColor = d.status === 'WAIT' ? '#2ea043' : d.status === 'REJECT' ? '#d29922' : d.status === 'PROPOSE_TRADE' ? '#f85149' : '#8b949e'

  if (!state || !md) return <div className='wrap'>Loading...</div>

  return <div className='wrap'>
    {state.notify_user && (
      <div className='panel' style={{borderColor:'#f85149', marginBottom:12}}>
        <strong style={{color:'#f85149'}}>PROPOSE_TRADE ALERT</strong>
        <p style={{margin:'6px 0'}}>{state.notify_user.message}</p>
        <button onClick={ackNotify}>Acknowledge</button>
      </div>
    )}
    <div className='top'>
      <div>
        <h2>BTC/USD 15m Paper Dashboard</h2>
        <div style={{fontSize:12,opacity:.8}}>
          Market update: {state.latest_market_data_time || '-'} | Scan: {state.latest_scan_time || '-'} | Decision: {state.latest_decision_time || '-'}
        </div>
      </div>
      <div style={{display:'flex',gap:8,alignItems:'center'}}>
        <span className='badge'>PAPER MODE</span>
        <span style={{background:statusColor,color:'#fff',padding:'6px 10px',borderRadius:999,fontWeight:700,fontSize:12}}>
          AUTO: {d.status || 'INSUFFICIENT_DATA'}
        </span>
        <span style={{fontSize:12,opacity:.85}}>at {state.latest_decision_time || '-'}</span>
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
        <p>R:R: {d.risk_reward_ratio}</p>
        <p style={{fontSize:12}}>{d.reason}</p>
        <hr />
        <h3>Account</h3>
        <p>Equity: {state.account_state.account_equity}</p>
        <p>Cash: {state.account_state.cash_available}</p>
        <p>Open Positions: {state.account_state.open_positions.length}</p>
        <p>Bid/Ask: {md.bid} / {md.ask}</p>
        <p>Spread: {md.spread} ({md.spread_pct.toFixed(6)}%)</p>
      </div>
    </div>

    <div className='panel' style={{marginTop:12}}>
      <h3>Recent Scan History</h3>
      <table className='rows' style={{width:'100%'}}>
        <thead><tr><th>Scan Time</th><th>Decision Time</th><th>Status</th><th>Regime</th><th>R:R</th><th>Reason</th></tr></thead>
        <tbody>
          {history.slice().reverse().map((r,i)=><tr key={i}><td>{r.timestamp}</td><td>{r.decision_time || '-'}</td><td>{r.status}</td><td>{r.regime_label}</td><td>{r.risk_reward_ratio}</td><td>{r.reason}</td></tr>)}
        </tbody>
      </table>
    </div>
  </div>
}
