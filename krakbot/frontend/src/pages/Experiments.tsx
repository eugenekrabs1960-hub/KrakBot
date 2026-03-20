import React, { useState } from 'react';
import { fmtTsLA, fmtUsd } from '../utils/format';

export default function Experiments({ runs, onRun, onRefresh }: any) {
  const [name, setName] = useState('exp-v1-risk-notional');
  const [path, setPath] = useState('risk.max_notional_per_trade');
  const [value, setValue] = useState('60');
  const [cycles, setCycles] = useState(40);
  const [control, setControl] = useState(false);

  return (
    <div>
      <h2>Experiment Harness v1 (Paper Only)</h2>
      <div className="section-sub">One change at a time. Fixed reset baseline ($10,000). Bounded cycle windows.</div>

      <div className="card" style={{ display: 'grid', gap: 10 }}>
        <div className="toolbar">
          <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Experiment name" />
          <input value={path} onChange={(e) => setPath(e.target.value)} placeholder="change_path" />
          <input value={value} onChange={(e) => setValue(e.target.value)} placeholder="change_value" />
          <label style={{ display: 'inline-flex', gap: 6, alignItems: 'center' }}><input type="checkbox" checked={control} onChange={(e)=>setControl(e.target.checked)} /> Control rerun</label>
          <input type="number" value={cycles} onChange={(e) => setCycles(Number(e.target.value || 40))} min={5} max={200} />
          <button className="btn" onClick={() => onRun({ name, change_path: path, change_value: Number.isFinite(Number(value)) ? Number(value) : value, cycles, include_control_rerun: control })}>Run</button>
          <button className="btn" onClick={onRefresh}>Refresh</button>
        </div>
      </div>

      <div className="card" style={{ marginTop: 12 }}>
        <h3 style={{ marginTop: 0 }}>Recent Runs</h3>
        <div className="table-wrap">
          <table>
            <thead><tr><th>Run</th><th>Name</th><th>Created (PT)</th><th>Status</th><th>Classification</th><th>Workflow</th><th>Change</th><th className="num">Cycles</th></tr></thead>
            <tbody>
              {(runs?.items || []).map((r: any) => (
                <tr key={r.run_id}>
                  <td>{r.run_id}</td>
                  <td>{r.name}</td>
                  <td>{fmtTsLA(r.created_at)}</td>
                  <td><span className={`badge ${r.status === 'completed' ? 'good' : 'warn'}`}>{r.status}</span></td>
                  <td><span className={`badge ${r.classification === 'keep' ? 'good' : r.classification === 'reject' ? 'bad' : 'watch'}`}>{r.classification || '-'}</span></td>
                  <td>{(r.methodology?.workflow || ['baseline','variant']).join(' → ')}</td><td>{r.spec?.one_change ? `${r.spec.one_change.path}: ${String(r.spec.one_change.new)}` : '-'}</td>
                  <td className="num">{r.spec?.cycles ?? '-'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
