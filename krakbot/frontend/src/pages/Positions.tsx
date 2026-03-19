import React from 'react';

export default function Positions({ data }: any) {
  const items = data?.items || [];
  return (
    <div>
      <h2>Open Paper Positions</h2>
      <div style={{ marginBottom: 8 }}>Mode: <b>{data?.mode || '-'}</b></div>
      {items.length === 0 ? (
        <div className="card">No current positions. Run cycles and check allow_trade outcomes.</div>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Coin</th>
                <th>Side</th>
                <th>Size</th>
                <th>Notional</th>
                <th>Entry</th>
                <th>Unrealized PnL</th>
                <th>Mode</th>
                <th>Setup</th>
                <th>Opened At</th>
              </tr>
            </thead>
            <tbody>
              {items.map((x: any) => (
                <tr key={x.symbol}>
                  <td>{x.coin}</td>
                  <td>{x.side}</td>
                  <td>{x.qty}</td>
                  <td>{x.notional_usd ?? '-'}</td>
                  <td>{x.entry_px ?? '-'}</td>
                  <td>{x.unrealized_pnl ?? '-'}</td>
                  <td>{x.mode}</td>
                  <td>{x.setup_type || '-'}</td>
                  <td>{x.opened_at || '-'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
