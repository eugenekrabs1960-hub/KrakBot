import React from 'react';
import ModeBadge from '../components/ModeBadge';

function Card({ title, children }: any) {
  return (
    <div className="card" style={{ marginTop: 12 }}>
      <h3 style={{ marginTop: 0 }}>{title}</h3>
      {children}
    </div>
  );
}

function KeyStat({ label, value, sub }: any) {
  return (
    <div className="card compact" style={{ minHeight: 86 }}>
      <div className="muted">{label}</div>
      <div className="kpi-value">{value}</div>
      {sub ? <div className="kpi-sub">{sub}</div> : null}
    </div>
  );
}

export default function Overview({ data, modelHealth, loopsStatus, loopsHistory, reconHistory, relayHistory, walletSummary, onRun }: any) {
  const mode = data?.mode || {};
  const perf = data?.performance_summary || {};
  const topCandidates = data?.top_candidates || [];
  const openPositions = data?.open_positions || [];
  const recentFills = data?.recent_trade_fills || [];
  const recentDecisions = data?.recent_decision_trace || [];
  const blocked = data?.recent_blocked_trades || [];
  const paperAccount = data?.paper_account || {};

  const safety = mode.execution_mode === 'paper' ? 'PAPER SAFE' : (mode.live_armed ? 'LIVE ARMED' : 'LIVE DISARMED');

  return (
    <div>
      <h2>Paper Trading Control Room</h2>

      <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap', marginBottom: 8 }}>
        <ModeBadge mode={mode.execution_mode || 'paper'} armed={!!mode.live_armed} />
        <span className={`badge ${mode.execution_mode === 'paper' ? 'good' : (mode.live_armed ? 'warn' : 'bad')}`}>{safety}</span>
        <span className={`badge ${mode.trading_enabled ? 'good' : 'bad'}`}>{mode.trading_enabled ? 'Trading Enabled' : 'Trading Disabled'}</span>
        <span className={`badge ${modelHealth?.ok ? 'good' : 'bad'}`}>Model Health: {modelHealth?.ok ? 'Online' : 'Offline'}</span>
        <button className="btn" onClick={onRun}>Run Decision Cycle</button>
      </div>

      <div className="grid kpi">
        <KeyStat label="Last Decision Cycle" value={data?.last_decision_cycle_at || loopsStatus?.last_decision_run_at || '-'} />
        <KeyStat label="Last Feature Loop" value={loopsStatus?.last_feature_run_at || '-'} />
        <KeyStat label="Open Positions" value={perf.total_open_positions ?? 0} sub="Paper positions" />
        <KeyStat label="Allowed Trades" value={perf.allowed_trade_count ?? 0} />
        <KeyStat label="Blocked Trades" value={perf.blocked_trade_count ?? 0} />
        <KeyStat label="Recent Trades" value={perf.recent_trade_count ?? 0} />
        <KeyStat label="Realized PnL" value={Number(perf.realized_pnl || 0).toFixed(2)} />
        <KeyStat label="Unrealized PnL" value={Number(perf.unrealized_pnl || 0).toFixed(2)} />
        <KeyStat label="Paper Cash" value={Number(paperAccount.cash_usd || 0).toFixed(2)} />
        <KeyStat label="Paper Equity" value={Number(paperAccount.total_equity_usd || 0).toFixed(2)} />
        <KeyStat label="Cumulative Fees" value={Number(paperAccount.cumulative_fees_usd || 0).toFixed(2)} />
      </div>

      <Card title="Candidate Watch">
        <div className="table-wrap">
          <table>
            <thead><tr><th>Rank</th><th>Coin</th><th>Recommendation</th><th>Confidence</th><th>Setup</th><th>Key Risks</th><th>Policy Result</th></tr></thead>
            <tbody>
              {topCandidates.map((c: any, i: number) => (
                <tr key={c.symbol}>
                  <td>{i + 1}</td>
                  <td>{c.coin}</td>
                  <td>{c.action || '-'}</td>
                  <td>{c.confidence != null ? Number(c.confidence).toFixed(3) : '-'}</td>
                  <td>{c.setup_type || '-'}</td>
                  <td>{(c.key_risks || []).join(', ') || '-'}</td>
                  <td>{c.policy_result || '-'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      <Card title="Active Paper Positions">
        {openPositions.length === 0 ? (
          <div className="muted">No current positions.</div>
        ) : (
          <div className="table-wrap">
            <table>
              <thead><tr><th>Coin</th><th>Side</th><th>Entry</th><th>Current</th><th>Unrealized PnL</th><th>Opened</th><th>Setup</th><th>Confidence</th></tr></thead>
              <tbody>
                {openPositions.map((p: any, i: number) => (
                  <tr key={i}>
                    <td>{p.coin}</td>
                    <td>{p.side}</td>
                    <td>{p.entry_price ?? '-'}</td>
                    <td>{p.current_price ?? '-'}</td>
                    <td>{Number(p.unrealized_pnl || 0).toFixed(3)}</td>
                    <td>{p.opened_at || '-'}</td>
                    <td>{p.setup_type || '-'}</td>
                    <td>{p.confidence != null ? Number(p.confidence).toFixed(3) : '-'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <Card title="Recent Trades / Fills">
        {recentFills.length === 0 ? (
          <div className="muted">No recent closed trade pairs yet.</div>
        ) : (
          <div className="table-wrap">
            <table>
              <thead><tr><th>Coin</th><th>Side</th><th>Entry</th><th>Exit</th><th>PnL</th><th>Duration</th><th>Setup</th></tr></thead>
              <tbody>
                {recentFills.map((t: any, i: number) => (
                  <tr key={i}>
                    <td>{t.coin}</td>
                    <td>{t.side}</td>
                    <td>{t.entry ?? '-'}</td>
                    <td>{t.exit ?? '-'}</td>
                    <td>{Number(t.pnl || 0).toFixed(4)}</td>
                    <td>{t.duration || '-'}</td>
                    <td>{t.setup_type || '-'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <Card title="Recent Decisions">
        <div className="table-wrap">
          <table>
            <thead><tr><th>Timestamp</th><th>Coin</th><th>Action</th><th>Setup</th><th>Confidence</th><th>Policy Result</th><th>Reason Summary</th></tr></thead>
            <tbody>
              {recentDecisions.slice(0, 15).map((d: any, i: number) => (
                <tr key={i}>
                  <td>{d.timestamp || '-'}</td>
                  <td>{d.coin || d.symbol}</td>
                  <td>{d.action}</td>
                  <td>{d.setup_type}</td>
                  <td>{Number(d.confidence || 0).toFixed(3)}</td>
                  <td>{d.policy_result || '-'}</td>
                  <td>{(d.reason_summary || []).join(', ')}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      <Card title="Recent Blocked Trades">
        {blocked.length === 0 ? (
          <div className="muted">No recent blocked trades.</div>
        ) : (
          <div className="table-wrap">
            <table>
              <thead><tr><th>Coin</th><th>Requested</th><th>Policy Result</th><th>Blocked Reason</th></tr></thead>
              <tbody>
                {blocked.slice(0, 15).map((b: any, i: number) => (
                  <tr key={i}><td>{b.coin}</td><td>{b.requested_action}</td><td>{b.final_action}</td><td>{b.downgrade_or_block_reason || '-'}</td></tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <Card title="System Health Panels">
        <div className="grid" style={{ gridTemplateColumns: '1fr 1fr 1fr', gap: 10 }}>
          <pre style={{ maxHeight: 180, overflow: 'auto' }}>{JSON.stringify(loopsHistory?.items || [], null, 2)}</pre>
          <pre style={{ maxHeight: 180, overflow: 'auto' }}>{JSON.stringify(reconHistory?.items || [], null, 2)}</pre>
          <pre style={{ maxHeight: 180, overflow: 'auto' }}>{JSON.stringify(relayHistory?.items || [], null, 2)}</pre>
        </div>
      </Card>

      <Card title="Model Runtime + Wallet Optional Signal">
        <div className="grid" style={{ gridTemplateColumns: '1fr 1fr', gap: 10 }}>
          <pre>{JSON.stringify(modelHealth || {}, null, 2)}</pre>
          <pre style={{ maxHeight: 180, overflow: 'auto' }}>{JSON.stringify(walletSummary?.items || data?.wallet_summaries || [], null, 2)}</pre>
        </div>
      </Card>
    </div>
  );
}
