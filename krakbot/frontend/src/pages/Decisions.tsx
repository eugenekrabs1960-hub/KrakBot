import React, { useMemo, useState } from 'react';
import { fmtNum, fmtTsLA } from '../utils/format';

const policyBadge = (s: string) => {
  if (!s) return 'badge neutral';
  if (s === 'allow_trade') return 'badge allow';
  if (s.includes('block')) return 'badge block';
  if (s.includes('watch') || s.includes('downgrade')) return 'badge watch';
  return 'badge neutral';
};

export default function Decisions({ data }: any) {
  const decisions = data?.decisions || [];
  const policy = data?.policy || [];
  const execution = data?.execution || [];

  const policyByPacket = useMemo(() => {
    const m: any = {};
    policy.forEach((p: any) => { if (p.packet_id) m[p.packet_id] = p; });
    return m;
  }, [policy]);

  const execByPacket = useMemo(() => {
    const m: any = {};
    execution.forEach((e: any) => { if (e.packet_id) m[e.packet_id] = e; });
    return m;
  }, [execution]);

  const [open, setOpen] = useState<string | null>(null);

  return (
    <div>
      <h2>Decision Timeline</h2>
      <div className="section-sub">Model decision, policy gate, and execution outcome in one place</div>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Time (PT)</th>
              <th>Coin</th>
              <th>Model Action</th>
              <th>Setup</th>
              <th className="num">Confidence</th>
              <th>Policy</th>
              <th>Execution</th>
              <th>Reason Summary</th>
              <th>Inspect</th>
            </tr>
          </thead>
          <tbody>
            {decisions.slice(0, 80).map((d: any, i: number) => {
              const p = policyByPacket[d.packet_id] || {};
              const e = execByPacket[d.packet_id] || {};
              const key = d.packet_id || `row-${i}`;
              return (
                <React.Fragment key={key}>
                  <tr>
                    <td>{fmtTsLA(d.generated_at)}</td>
                    <td>{d.coin || d.symbol}</td>
                    <td>{d.action}</td>
                    <td>{d.setup_type}</td>
                    <td className="num">{fmtNum(d.confidence, 3)}</td>
                    <td><span className={policyBadge(p.final_action)}>{p.final_action || '-'}</span></td>
                    <td><span className={`badge ${e.status === 'filled' ? 'good' : e.status === 'rejected' ? 'bad' : 'neutral'}`}>{e.status || '-'}</span></td>
                    <td>{(d.reasons || []).slice(0, 2).map((r: any) => r.label).join(', ') || '-'}</td>
                    <td><button className="btn" onClick={() => setOpen(open === key ? null : key)}>{open === key ? 'Hide' : 'View'}</button></td>
                  </tr>
                  {open === key && (
                    <tr>
                      <td colSpan={9}>
                        <div className="grid" style={{ gridTemplateColumns: '1fr 1fr 1fr', gap: 10 }}>
                          <div>
                            <h4>Decision</h4>
                            <pre>{JSON.stringify({
                              packet_id: d.packet_id,
                              thesis: d.thesis_summary,
                              reasons: d.reasons,
                              risks: d.risks,
                              invalidation: d.invalidation,
                              targets: d.targets,
                            }, null, 2)}</pre>
                          </div>
                          <div>
                            <h4>Policy Gate</h4>
                            <pre>{JSON.stringify({
                              final_action: p.final_action,
                              requested_action: p.requested_action,
                              downgrade_or_block_reason: p.downgrade_or_block_reason,
                              gate_checks: p.gate_checks,
                              reasons: p.reasons,
                            }, null, 2)}</pre>
                          </div>
                          <div>
                            <h4>Execution</h4>
                            <pre>{JSON.stringify(e || {}, null, 2)}</pre>
                          </div>
                        </div>
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
