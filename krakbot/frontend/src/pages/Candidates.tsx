import React from 'react';

function shortList(xs: any[] = [], key = 'label', cap = 2) {
  if (!xs || xs.length === 0) return '-';
  return xs.slice(0, cap).map((x: any) => x?.[key] || JSON.stringify(x)).join(', ');
}

export default function Candidates({ data }: any) {
  const items = data?.items || [];
  return (
    <div>
      <h2>Candidate Inspector</h2>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Rank</th>
              <th>Coin / Symbol</th>
              <th>Scores (A/O/T)</th>
              <th>Model Recommendation</th>
              <th>Setup</th>
              <th>Confidence</th>
              <th>Reasons</th>
              <th>Risks</th>
              <th>Policy Result</th>
              <th>Blocked Reason</th>
              <th>Packet Context</th>
              <th>Wallet Status</th>
            </tr>
          </thead>
          <tbody>
            {items.map((x: any, i: number) => (
              <tr key={x.symbol}>
                <td>{i + 1}</td>
                <td><b>{x.coin}</b><div className="muted">{x.symbol}</div></td>
                <td>{Number(x.ml_scores?.attention_score || 0).toFixed(3)} / {Number(x.ml_scores?.opportunity_score || 0).toFixed(3)} / {Number(x.ml_scores?.tradability_score || 0).toFixed(3)}</td>
                <td>{x.latest_decision?.action || '-'}</td>
                <td>{x.latest_decision?.setup_type || '-'}</td>
                <td>{x.latest_decision?.confidence != null ? Number(x.latest_decision.confidence).toFixed(3) : '-'}</td>
                <td>{shortList(x.latest_decision?.reasons, 'label', 2)}</td>
                <td>{shortList(x.latest_decision?.risks, 'label', 2)}</td>
                <td>{x.latest_policy?.final_action || '-'}</td>
                <td>{x.latest_policy?.block_reason || '-'}</td>
                <td>
                  contradiction: {x.packet_context?.contradiction_score ?? '-'}<br/>
                  extension: {x.packet_context?.extension_score ?? '-'}<br/>
                  tq_prior: {x.packet_context?.trade_quality_prior ?? '-'}<br/>
                  regime_compat: {x.packet_context?.regime_compatibility_score ?? '-'}
                </td>
                <td>
                  {x.wallet_summary ? (
                    <>
                      {x.wallet_summary.net_flow_bias}<br/>
                      conv={x.wallet_summary.wallet_conviction_score}
                    </>
                  ) : 'wallet summary unavailable'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
