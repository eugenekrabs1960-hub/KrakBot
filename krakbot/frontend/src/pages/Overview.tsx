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
    <div className="card compact" style={{ minHeight: 84 }}>
      <div className="muted">{label}</div>
      <div className="kpi-value">{value}</div>
      {sub ? <div className="kpi-sub">{sub}</div> : null}
    </div>
  );
}

export default function Overview({ data, modelHealth, loopsStatus, loopsHistory, reconHistory, relayHistory, walletSummary, onRun }: any) {
  const mode = data?.mode || {};
  const candidates = (data?.tracked_universe?.tracked_coins || []).join(', ');
  const topAllowed = data?.recent_allowed_trades || [];
  const topBlocked = data?.recent_blocked_trades || [];
  const blockReasons = data?.dominant_block_reasons || {};

  const lastDecision = loopsStatus?.last_decision_run_at || '-';
  const lastFeature = loopsStatus?.last_feature_run_at || '-';

  return (
    <div>
      <h2>Control Room</h2>

      <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap', marginBottom: 8 }}>
        <ModeBadge mode={mode.execution_mode || 'paper'} armed={!!mode.live_armed} />
        <span className={`badge ${mode.trading_enabled ? 'good' : 'bad'}`}>{mode.trading_enabled ? 'Trading Enabled' : 'Trading Disabled'}</span>
        <span className={`badge ${modelHealth?.ok ? 'good' : 'bad'}`}>Model Health: {modelHealth?.ok ? 'Online' : 'Offline'}</span>
        <button className="btn" onClick={onRun}>Run Decision Cycle</button>
      </div>

      <div className="grid kpi">
        <KeyStat label="Execution Mode" value={mode.execution_mode || '-'} sub={mode.live_armed ? 'Live armed' : 'Live disarmed'} />
        <KeyStat label="Last Decision Cycle" value={lastDecision} />
        <KeyStat label="Last Feature Loop" value={lastFeature} />
        <KeyStat label="Open Positions" value={data?.open_positions_count ?? 0} sub="Paper positions" />
        <KeyStat label="Tracked Coins" value={(data?.tracked_universe?.tracked_coins || []).length} sub={candidates || '-'} />
        <KeyStat label="Recent Allowed Trades" value={topAllowed.length} />
      </div>

      <Card title="Current Top Candidates / Watchlist">
        <div>{candidates || '-'}</div>
      </Card>

      <Card title="Recent Blocked Trades (dominant reasons)">
        {Object.keys(blockReasons).length === 0 ? (
          <div className="muted">No recent blocked trades.</div>
        ) : (
          <ul>
            {Object.entries(blockReasons).map(([k, v]: any) => <li key={k}><b>{k}</b>: {v}</li>)}
          </ul>
        )}
      </Card>

      <Card title="Recent Allowed Trades">
        {topAllowed.length === 0 ? (
          <div className="muted">No recent allowed trades.</div>
        ) : (
          <div className="table-wrap">
            <table>
              <thead><tr><th>Coin</th><th>Action</th><th>Policy Result</th></tr></thead>
              <tbody>
                {topAllowed.slice(0, 10).map((x: any, i: number) => (
                  <tr key={i}><td>{x.coin}</td><td>{x.requested_action}</td><td>{x.final_action}</td></tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <Card title="Model Runtime">
        <pre>{JSON.stringify(modelHealth || {}, null, 2)}</pre>
      </Card>

      <Card title="Wallet Summary (Read-Only Optional Signal)">
        <pre style={{ maxHeight: 180, overflow: 'auto' }}>{JSON.stringify(walletSummary?.items || data?.wallet_summaries || [], null, 2)}</pre>
      </Card>

      <Card title="Loop / Reconciliation / Relay Health">
        <div style={{ marginBottom: 8 }}>
          Last error: {loopsStatus?.last_error || 'none'}
        </div>
        <div className="grid" style={{ gridTemplateColumns: '1fr 1fr 1fr', gap: 10 }}>
          <pre style={{ maxHeight: 180, overflow: 'auto' }}>{JSON.stringify(loopsHistory?.items || [], null, 2)}</pre>
          <pre style={{ maxHeight: 180, overflow: 'auto' }}>{JSON.stringify(reconHistory?.items || [], null, 2)}</pre>
          <pre style={{ maxHeight: 180, overflow: 'auto' }}>{JSON.stringify(relayHistory?.items || [], null, 2)}</pre>
        </div>
      </Card>

      <Card title="Safety State">
        <ul>
          <li>Mode: <b>{mode.execution_mode || '-'}</b></li>
          <li>Live armed: <b>{String(!!mode.live_armed)}</b></li>
          <li>Trading enabled: <b>{String(mode.trading_enabled ?? true)}</b></li>
          <li>If live is disarmed, trades are blocked by policy.</li>
        </ul>
      </Card>
    </div>
  );
}
