import React from 'react';
import { fmtNum, fmtUsd, fmtTsLA, pnlClass } from '../utils/format';

export default function Positions({ data, tradesData }: any) {
  const summary = data?.summary_items || data?.items || [];
  const openLegs = data?.open_legs || [];
  const trades = tradesData?.execution || tradesData?.items || [];

  const closed = trades
    .filter((t: any) => (t?.status || '').toLowerCase() === 'filled')
    .slice(0, 20)
    .map((t: any) => {
      const pnl = Number(t?.pnl_usd ?? t?.realized_pnl_usd ?? t?.outcomes?.realized_pnl_usd ?? 0);
      return {
        symbol: t?.symbol || '-',
        coin: (t?.symbol || '').replace('-PERP', ''),
        action: t?.action || '-',
        notional: t?.filled_notional_usd ?? t?.notional_usd,
        fee: t?.fee_usd,
        pnl,
        ts: t?.created_at || t?.closed_at || t?.ts,
      };
    });

  return (
    <div>
      <h2>Aggregated Positions</h2>
      <div className="section-sub">Symbol-level summary view</div>
      <div style={{ marginBottom: 10 }}>Mode: <span className="badge info2">{data?.mode || '-'}</span></div>

      {summary.length === 0 ? (
        <div className="card">No aggregated open positions right now.</div>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Coin</th>
                <th>Side</th>
                <th className="num">Net Size</th>
                <th className="num">Notional</th>
                <th className="num">Leverage (weighted)</th>
                <th className="num">Avg Entry</th>
                <th className="num">Mark</th>
                <th className="num">Unrealized PnL</th>
                <th>Setup</th>
                <th>Opened (PT)</th>
              </tr>
            </thead>
            <tbody>
              {summary.map((x: any) => (
                <tr key={x.symbol}>
                  <td>{x.coin}</td>
                  <td><span className={`badge ${x.side === 'long' ? 'good' : 'bad'}`}>{x.side}</span></td>
                  <td className="num">{fmtNum(x.qty, 3)}</td>
                  <td className="num">{fmtUsd(x.notional_usd)}</td>
                  <td className="num">{fmtNum(x.leverage ?? 1.0, 2)}x</td>
                  <td className="num">{fmtUsd(x.entry_px)}</td>
                  <td className="num">{fmtUsd(x.mark_px)}</td>
                  <td className={`num value ${pnlClass(x.unrealized_pnl)}`}>{fmtUsd(x.unrealized_pnl)}</td>
                  <td>{x.setup_type || '-'}</td>
                  <td>{fmtTsLA(x.opened_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="card" style={{ marginTop: 14 }}>
        <h3 style={{ marginTop: 0 }}>Open Trades</h3>
        <div className="section-sub" style={{ marginTop: 0 }}>Each open trade shown separately</div>

        {openLegs.length === 0 ? (
          <div className="muted">No open trades right now.</div>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Coin</th>
                  <th>Side</th>
                  <th className="num">Qty</th>
                  <th className="num">Entry Notional</th>
                  <th className="num">Leverage (entry)</th>
                  <th className="num">Entry</th>
                  <th className="num">Mark</th>
                  <th className="num">Unrealized PnL</th>
                  <th className="num">Stop Loss</th>
                  <th className="num">Take Profit</th>
                  <th>Exit Trigger</th>
                  <th>Setup</th>
                  <th>Opened (PT)</th>
                </tr>
              </thead>
              <tbody>
                {openLegs.map((x: any) => (
                  <tr key={x.leg_id || `${x.symbol}-${x.packet_id}`}>
                    <td>{x.coin}</td>
                    <td><span className={`badge ${x.side === 'long' ? 'good' : 'bad'}`}>{x.side}</span></td>
                    <td className="num">{fmtNum(x.remaining_qty ?? x.entry_qty, 4)}</td>
                    <td className="num">{fmtUsd(x.entry_notional_usd)}</td>
                    <td className="num">{fmtNum(x.leverage ?? 1.0, 1)}x</td>
                    <td className="num">{fmtUsd(x.entry_px)}</td>
                    <td className="num">{fmtUsd(x.mark_px)}</td>
                    <td className={`num value ${pnlClass(x.unrealized_pnl)}`}>{fmtUsd(x.unrealized_pnl)}</td>
                    <td className="num">{x.stop_loss != null ? fmtUsd(x.stop_loss) : 'Not set'}</td>
                    <td className="num">{x.take_profit != null ? fmtUsd(x.take_profit) : 'Not set'}</td>
                    <td>{x.invalidation?.type || 'Not set'}</td>
                    <td>{x.setup_type || '-'}</td>
                    <td>{fmtTsLA(x.opened_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="card" style={{ marginTop: 14 }}>
        <h3 style={{ marginTop: 0 }}>Recent Closed Trades</h3>
        <div className="section-sub" style={{ marginTop: 0 }}>Most recent filled paper executions (realized PnL may be unavailable)</div>
        {closed.length === 0 ? (
          <div className="muted">No recent closed trades.</div>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Coin</th>
                  <th>Action</th>
                  <th className="num">Notional</th>
                  <th className="num">Fee</th>
                  <th className="num">PnL</th>
                  <th>Closed (PT)</th>
                </tr>
              </thead>
              <tbody>
                {closed.map((t: any, i: number) => (
                  <tr key={`${t.symbol}-${i}`}>
                    <td>{t.coin || t.symbol}</td>
                    <td><span className={`badge ${t.action === 'long' ? 'good' : t.action === 'short' ? 'bad' : 'neutral'}`}>{t.action}</span></td>
                    <td className="num">{fmtUsd(t.notional)}</td>
                    <td className="num">{fmtUsd(t.fee)}</td>
                    <td className={`num value ${pnlClass(t.pnl)}`}>{fmtUsd(t.pnl)}</td>
                    <td>{fmtTsLA(t.ts)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
