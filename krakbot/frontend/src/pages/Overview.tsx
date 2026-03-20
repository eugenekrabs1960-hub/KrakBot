import React from 'react';
import ModeBadge from '../components/ModeBadge';
import { fmtNum, fmtUsd, fmtTsLA, pnlClass } from '../utils/format';

function Card({ title, children }: any) {
  return (
    <div className="card" style={{ marginTop: 12 }}>
      <h3 style={{ marginTop: 0 }}>{title}</h3>
      {children}
    </div>
  );
}

function KeyStat({ label, value, sub, cls }: any) {
  return (
    <div className="card compact" style={{ minHeight: 86 }}>
      <div className="muted">{label}</div>
      <div className={`kpi-value value ${cls || 'neutral'}`}>{value}</div>
      {sub ? <div className="kpi-sub">{sub}</div> : null}
    </div>
  );
}

const policyBadge = (s: string) => {
  if (!s) return 'badge neutral';
  if (s === 'allow_trade') return 'badge allow';
  if (s.includes('block')) return 'badge block';
  if (s.includes('watch') || s.includes('downgrade')) return 'badge watch';
  return 'badge neutral';
};

export default function Overview({ data, modelHealth, loopsStatus, loopsHistory, reconHistory, relayHistory, walletSummary, onRun }: any) {
  const mode = data?.mode || {};
  const perf = data?.performance_summary || {};
  const topCandidates = data?.top_candidates || [];
  const openPositions = data?.open_positions || [];
  const recentFills = data?.recent_trade_fills || [];
  const recentDecisions = data?.recent_decision_trace || [];
  const blocked = data?.recent_blocked_trades || [];
  const paperAccount = data?.paper_account || {};
  const newsSignals = data?.latest_news_signals || {};
  const communitySignals = data?.latest_community_signals || {};
  const featureStatus = data?.latest_feature_status || {};

  const safety = mode.execution_mode === 'paper' ? 'Paper Safe' : (mode.live_armed ? 'Live Armed' : 'Live Disarmed');

  return (
    <div>
      <h2>Paper Trading Control Room</h2>
      <div className="section-sub">Readable, real-time paper evaluation dashboard</div>

      <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap', marginBottom: 8 }}>
        <ModeBadge mode={mode.execution_mode || 'paper'} armed={!!mode.live_armed} />
        <span className={`badge ${mode.execution_mode === 'paper' ? 'good' : (mode.live_armed ? 'warn' : 'bad')}`}>{safety}</span>
        <span className={`badge ${mode.trading_enabled ? 'good' : 'bad'}`}>{mode.trading_enabled ? 'Trading Enabled' : 'Trading Disabled'}</span>
        <span className={`badge ${modelHealth?.ok ? 'good' : 'bad'}`}>Model {modelHealth?.ok ? 'Online' : 'Offline'}</span>
        <span className={`badge ${loopsStatus?.running ? 'good' : 'warn'}`}>Loop {loopsStatus?.running ? 'Running' : 'Stopped'}</span>
        <span className={`badge ${loopsStatus?.model_backoff_active ? 'block' : 'neutral'}`}>Backoff {loopsStatus?.model_backoff_active ? 'Active' : 'Idle'}</span>
        <button className="btn" onClick={onRun}>Run Paper Cycle</button>
      </div>

      <div className="grid kpi">
        <KeyStat label="Last Decision Cycle" value={fmtTsLA(data?.last_decision_cycle_at || loopsStatus?.last_decision_run_at)} />
        <KeyStat label="Last Feature Loop" value={fmtTsLA(loopsStatus?.last_feature_run_at)} />
        <KeyStat label="Model Cooldown Until" value={fmtTsLA(loopsStatus?.model_cooldown_until)} />
        <KeyStat label="Offline Events" value={loopsStatus?.model_offline_events ?? 0} />
        <KeyStat label="Open Positions" value={perf.total_open_positions ?? 0} sub="Current paper positions" />
        <KeyStat label="Allowed Trades" value={perf.allowed_trade_count ?? 0} />
        <KeyStat label="Blocked Trades" value={perf.blocked_trade_count ?? 0} />
        <KeyStat label="Recent Trades" value={perf.recent_trade_count ?? 0} />
        <KeyStat label="Realized PnL" value={fmtUsd(perf.realized_pnl || 0)} cls={pnlClass(perf.realized_pnl || 0)} />
        <KeyStat label="Unrealized PnL" value={fmtUsd(perf.unrealized_pnl || 0)} cls={pnlClass(perf.unrealized_pnl || 0)} />
        <KeyStat label="Paper Cash" value={fmtUsd(paperAccount.cash_usd || 0)} />
        <KeyStat label="Paper Equity" value={fmtUsd(paperAccount.total_equity_usd || 0)} cls={pnlClass((paperAccount.total_equity_usd || 0) - 10000)} />
        <KeyStat label="Cumulative Fees" value={fmtUsd(paperAccount.cumulative_fees_usd || 0)} className="neutral" />
      </div>


      <Card title="Market Data / Feature Engine Health">
        <div className="table-wrap">
          <table>
            <thead><tr><th>Coin</th><th>Market Source</th><th className="num">Completeness</th><th className="num">Source Health</th><th>Status</th><th>Reason</th></tr></thead>
            <tbody>
              {Object.keys(featureStatus).length === 0 ? (
                <tr><td colSpan={6} className="muted">No feature status yet.</td></tr>
              ) : (
                Object.entries(featureStatus).map(([coin, fs]: any) => (
                  <tr key={coin}>
                    <td>{coin}</td>
                    <td>{fs?.market_source || '-'}</td>
                    <td className="num">{fmtNum(fs?.data_completeness_score, 3)}</td>
                    <td className="num">{fmtNum(fs?.source_health_score, 3)}</td>
                    <td><span className={`badge ${fs?.degraded ? 'block' : 'allow'}`}>{fs?.degraded ? 'Degraded' : 'Healthy'}</span></td>
                    <td>{fs?.reason || '-'}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </Card>

      <Card title="Top Candidate Watchlist">
        <div className="table-wrap">
          <table>
            <thead><tr><th>Rank</th><th>Coin</th><th>Action</th><th className="num">Confidence</th><th>Setup</th><th>Key Risks</th><th>Status</th></tr></thead>
            <tbody>
              {topCandidates.map((c: any, i: number) => (
                <tr key={c.symbol}>
                  <td>{i + 1}</td>
                  <td>{c.coin}</td>
                  <td>{c.action || '-'}</td>
                  <td className="num">{fmtNum(c.confidence, 3)}</td>
                  <td>{c.setup_type || '-'}</td>
                  <td>{(c.key_risks || []).join(', ') || '-'}</td>
                  <td><span className={policyBadge(c.policy_result)}>{c.policy_result || 'neutral'}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      <Card title="Open Paper Positions">
        {openPositions.length === 0 ? <div className="muted">No open paper positions right now.</div> : (
          <div className="table-wrap">
            <table>
              <thead><tr><th>Coin</th><th>Side</th><th className="num">Entry</th><th className="num">Mark</th><th className="num">Unrealized PnL</th><th>Opened</th><th>Setup</th><th className="num">Confidence</th></tr></thead>
              <tbody>
                {openPositions.map((p: any, i: number) => (
                  <tr key={i}>
                    <td>{p.coin}</td>
                    <td><span className={`badge ${p.side === 'long' ? 'good' : 'bad'}`}>{p.side}</span></td>
                    <td className="num">{fmtUsd(p.entry_price)}</td>
                    <td className="num">{fmtUsd(p.current_price)}</td>
                    <td className={`num value ${pnlClass(p.unrealized_pnl)}`}>{fmtUsd(p.unrealized_pnl)}</td>
                    <td>{fmtTsLA(p.opened_at)}</td>
                    <td>{p.setup_type || '-'}</td>
                    <td className="num">{fmtNum(p.confidence, 3)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <Card title="Recent Closed Trades">
        {recentFills.length === 0 ? <div className="muted">No closed paper trades yet.</div> : (
          <div className="table-wrap">
            <table>
              <thead><tr><th>Coin</th><th>Side</th><th className="num">Entry</th><th className="num">Exit</th><th className="num">PnL</th><th>Opened</th><th>Closed</th><th>Setup</th></tr></thead>
              <tbody>
                {recentFills.map((t: any, i: number) => (
                  <tr key={i}>
                    <td>{t.coin}</td>
                    <td><span className={`badge ${t.side === 'long' ? 'good' : 'bad'}`}>{t.side}</span></td>
                    <td className="num">{fmtUsd(t.entry)}</td>
                    <td className="num">{fmtUsd(t.exit)}</td>
                    <td className={`num value ${pnlClass(t.pnl)}`}>{fmtUsd(t.pnl)}</td>
                    <td>{fmtTsLA(t.opened_at)}</td>
                    <td>{fmtTsLA(t.closed_at)}</td>
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
            <thead><tr><th>Time (PT)</th><th>Coin</th><th>Action</th><th>Setup</th><th className="num">Confidence</th><th>Status</th><th>Reason Summary</th></tr></thead>
            <tbody>
              {recentDecisions.slice(0, 15).map((d: any, i: number) => (
                <tr key={i}>
                  <td>{fmtTsLA(d.timestamp)}</td>
                  <td>{d.coin || d.symbol}</td>
                  <td>{d.action}</td>
                  <td>{d.setup_type}</td>
                  <td className="num">{fmtNum(d.confidence, 3)}</td>
                  <td><span className={policyBadge(d.policy_result)}>{d.policy_result || '-'}</span></td>
                  <td>{(d.reason_summary || []).join(', ')}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      <Card title="Recent Blocked Decisions">
        {blocked.length === 0 ? (
          <div className="muted">No recently blocked decisions.</div>
        ) : (
          <div className="table-wrap">
            <table>
              <thead><tr><th>Coin</th><th>Requested</th><th>Status</th><th>Reason</th></tr></thead>
              <tbody>
                {blocked.slice(0, 15).map((b: any, i: number) => (
                  <tr key={i}><td>{b.coin}</td><td>{b.requested_action}</td><td><span className={policyBadge(b.final_action)}>{b.final_action}</span></td><td>{b.downgrade_or_block_reason || '-'}</td></tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <Card title="System Panels">
        <div className="grid" style={{ gridTemplateColumns: '1fr 1fr 1fr', gap: 10 }}>
          <pre style={{ maxHeight: 180, overflow: 'auto' }}>{JSON.stringify(loopsHistory?.items || [], null, 2)}</pre>
          <pre style={{ maxHeight: 180, overflow: 'auto' }}>{JSON.stringify(reconHistory?.items || [], null, 2)}</pre>
          <pre style={{ maxHeight: 180, overflow: 'auto' }}>{JSON.stringify(relayHistory?.items || [], null, 2)}</pre>
        </div>
      </Card>


      <Card title="Trending / Community Heat">
        <div className="muted" style={{ marginBottom: 6 }}>Daily community attention summary (not a direct trade trigger). Community bias is a lightweight proxy, not full social sentiment analysis.</div>
        <div className="table-wrap">
          <table>
            <thead><tr><th>Coin</th><th className="num">Mention Velocity</th><th className="num">Trendiness</th><th className="num">Community Bias (proxy)</th><th className="num">Hype</th><th className="num">Crowding Risk</th><th>Summary</th></tr></thead>
            <tbody>
              {Object.keys(communitySignals).length === 0 ? (
                <tr><td colSpan={7} className="muted">No community summary yet.</td></tr>
              ) : (
                Object.entries(communitySignals).map(([coin, cs]: any) => (
                  <tr key={coin}>
                    <td>{coin}</td>
                    <td className="num">{fmtNum(cs?.mention_velocity_score, 3)}</td>
                    <td className="num">{fmtNum(cs?.trendiness_score, 3)}</td>
                    <td className="num">{fmtNum(cs?.community_bias_score, 3)}</td>
                    <td className="num">{fmtNum(cs?.hype_score, 3)}</td>
                    <td className="num">{fmtNum(cs?.crowding_risk, 3)}</td>
                    <td>{cs?.summary_text || '-'}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </Card>

      <Card title="Model, Wallet, and News Signals">
        <div className="grid" style={{ gridTemplateColumns: '1fr 1fr', gap: 10 }}>
          <pre>{JSON.stringify(modelHealth || {}, null, 2)}</pre>
          <pre style={{ maxHeight: 180, overflow: 'auto' }}>{JSON.stringify(walletSummary?.items || data?.wallet_summaries || [], null, 2)}</pre>
        </div>
        <div className="muted" style={{ marginBottom: 6 }}>Priced-in Risk is a hybrid signal (news context + market microstructure), not RSS-only.</div>
        <div className="table-wrap" style={{ marginTop: 10 }}>
          <table>
            <thead><tr><th>Coin</th><th className="num">Community Bias (proxy)</th><th className="num">Novelty</th><th className="num">Freshness</th><th className="num">Priced-in Risk (hybrid)</th><th>Summary</th></tr></thead>
            <tbody>
              {Object.keys(newsSignals).length === 0 ? (
                <tr><td colSpan={6} className="muted">No news summary yet.</td></tr>
              ) : (
                Object.entries(newsSignals).map(([coin, ns]: any) => (
                  <tr key={coin}>
                    <td>{coin}</td>
                    <td className="num">{fmtNum(ns?.sentiment_score, 3)}</td>
                    <td className="num">{fmtNum(ns?.novelty_score, 3)}</td>
                    <td className="num">{fmtNum(ns?.freshness_score, 3)}</td>
                    <td className="num">{fmtNum(ns?.priced_in_risk_score, 3)}</td>
                    <td>{ns?.summary_text || '-'}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
