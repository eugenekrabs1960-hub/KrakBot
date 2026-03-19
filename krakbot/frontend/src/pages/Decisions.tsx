import React from 'react';

export default function Decisions({ data }: any) {
  const decisions = data?.decisions || [];
  const policy = data?.policy || [];
  const execution = data?.execution || [];

  return (
    <div>
      <h2>Decisions</h2>
      <h3>Recent Decision Outputs</h3>
      <table>
        <thead>
          <tr>
            <th>Symbol</th>
            <th>Action</th>
            <th>Setup</th>
            <th>Confidence</th>
            <th>Thesis</th>
          </tr>
        </thead>
        <tbody>
          {decisions.slice(0, 50).map((d: any, i: number) => (
            <tr key={i}>
              <td>{d.symbol}</td>
              <td>{d.action}</td>
              <td>{d.setup_type}</td>
              <td>{Number(d.confidence || 0).toFixed(3)}</td>
              <td>{d.thesis_summary}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <h3 style={{ marginTop: 16 }}>Policy Results</h3>
      <table>
        <thead>
          <tr>
            <th>Symbol</th>
            <th>Requested</th>
            <th>Final</th>
            <th>Reason</th>
          </tr>
        </thead>
        <tbody>
          {policy.slice(0, 50).map((p: any, i: number) => (
            <tr key={i}>
              <td>{p.symbol}</td>
              <td>{p.requested_action}</td>
              <td>{p.final_action}</td>
              <td>{p.downgrade_or_block_reason || (p.reasons || []).join(', ')}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <h3 style={{ marginTop: 16 }}>Execution Outcomes</h3>
      <table>
        <thead>
          <tr>
            <th>Symbol</th>
            <th>Action</th>
            <th>Status</th>
            <th>Notional</th>
            <th>Reason</th>
          </tr>
        </thead>
        <tbody>
          {execution.slice(0, 50).map((e: any, i: number) => (
            <tr key={i}>
              <td>{e.symbol}</td>
              <td>{e.action}</td>
              <td>{e.status}</td>
              <td>{e.filled_notional_usd ?? e.notional_usd ?? '-'}</td>
              <td>{e.reason || '-'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
