import React from 'react';

export default function Positions({ data }: any) {
  const items = data?.items || [];
  return (
    <div>
      <h2>Positions</h2>
      <div style={{ marginBottom: 8 }}>Mode: <b>{data?.mode || '-'}</b></div>
      <table>
        <thead>
          <tr>
            <th>Symbol</th>
            <th>Qty</th>
            <th>Entry</th>
            <th>Unrealized PnL</th>
          </tr>
        </thead>
        <tbody>
          {items.map((x: any) => (
            <tr key={x.symbol}>
              <td>{x.symbol}</td>
              <td>{x.qty}</td>
              <td>{x.entry_px ?? '-'}</td>
              <td>{x.unrealized_pnl ?? '-'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
