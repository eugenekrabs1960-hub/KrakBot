import React from 'react';

export default function Candidates({ data }: any) {
  const items = data?.items || [];
  return (
    <div>
      <h2>Candidates</h2>
      <table>
        <thead>
          <tr>
            <th>Coin</th>
            <th>Rank</th>
            <th>Opportunity</th>
            <th>Tradability</th>
            <th>Wallet Bias</th>
            <th>Wallet Conviction</th>
          </tr>
        </thead>
        <tbody>
          {items.map((x: any) => (
            <tr key={x.symbol}>
              <td>{x.coin}</td>
              <td>{Number(x.rank_score || 0).toFixed(3)}</td>
              <td>{Number(x.ml_scores?.opportunity_score || 0).toFixed(3)}</td>
              <td>{Number(x.ml_scores?.tradability_score || 0).toFixed(3)}</td>
              <td>{x.wallet_summary?.net_flow_bias || '-'}</td>
              <td>{x.wallet_summary?.wallet_conviction_score ?? '-'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
