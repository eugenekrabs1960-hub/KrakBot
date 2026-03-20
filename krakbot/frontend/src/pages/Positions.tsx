import React from 'react';
import { fmtNum, fmtUsd, fmtTsLA, pnlClass } from '../utils/format';

export default function Positions({ data }: any) {
  const items = data?.items || [];
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
    </div>
  );
}
