import React from 'react';
import { fmtNum, fmtUsd, fmtTsLA, pnlClass } from '../utils/format';

export default function Positions({ data, tradesData }: any) {
  const items = data?.items || [];
  const trades = tradesData?.items || [];

  const closed = trades
    .filter((t: any) => (t?.status || '').toLowerCase() === 'filled')
    .slice(0, 20)
    .map((t: any) => {
      const pnl = Number(t?.pnl_usd ?? t?.realized_pnl_usd ?? 0);
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
      <h2>Open Positions</h2>
      <div className="section-sub">Live view of currently open paper positions</div>
      <div style={{ marginBottom: 10 }}>Mode: <span className="badge info2">{data?.mode || '-'}</span></div>

      {items.length === 0 ? (
        <div className="card">No open positions right now.</div>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Coin</th>
                <th>Side</th>
                <th className="num">Size</th>
                <th className="num">Notional</th>
                <th className="num">Leverage</th>
                <th className="num">Entry</th>
                <th className="num">Mark</th>
                <th className="num">Unrealized PnL</th>
                <th>Setup</th>
                <th>Opened (PT)</th>
              </tr>
            </thead>
            <tbody>
              {items.map((x: any) => (
                <tr key={x.symbol}>
                  <td>{x.coin}</td>
                  <td><span className={`badge ${x.side === 'long' ? 'good' : 'bad'}`}>{x.side}</span></td>
                  <td className="num">{fmtNum(x.qty, 3)}</td>
                  <td className="num">{fmtUsd(x.notional_usd)}</td>
                  <td className="num">{fmtNum(x.leverage ?? 1.0, 1)}x</td>
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
        <h3 style={{ marginTop: 0 }}>Recent Closed Trades</h3>
        <div className="section-sub" style={{ marginTop: 0 }}>Most recent filled paper trades</div>
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
