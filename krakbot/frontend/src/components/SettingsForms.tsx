import React, { useState } from 'react';

export default function SettingsForms({ initial, onSave }: any) {
  const [s, setS] = useState(initial);
  if (!s) return null;
  return (
    <div style={{ display: 'grid', gap: 8 }}>
      <label>Execution Mode
        <select value={s.mode.execution_mode} onChange={e => setS({ ...s, mode: { ...s.mode, execution_mode: e.target.value } })}>
          <option value="paper">paper</option>
          <option value="live_hyperliquid">live_hyperliquid</option>
        </select>
      </label>
      <label>Live Armed <input type="checkbox" checked={s.mode.live_armed} onChange={e => setS({ ...s, mode: { ...s.mode, live_armed: e.target.checked } })} /></label>
      <label>Tracked Coins (comma)
        <input value={s.universe.tracked_coins.join(',')} onChange={e => setS({ ...s, universe: { ...s.universe, tracked_coins: e.target.value.split(',').map((x:string)=>x.trim()).filter(Boolean)}})} />
      </label>
      <label>Max candidates per cycle <input type="number" value={s.universe.max_candidates_per_cycle} onChange={e => setS({ ...s, universe: { ...s.universe, max_candidates_per_cycle: Number(e.target.value)}})} /></label>
      <label>Feature refresh seconds <input type="number" value={s.loop.feature_refresh_seconds} onChange={e => setS({ ...s, loop: { ...s.loop, feature_refresh_seconds: Number(e.target.value)}})} /></label>
      <label>Decision cycle seconds <input type="number" value={s.loop.decision_cycle_seconds} onChange={e => setS({ ...s, loop: { ...s.loop, decision_cycle_seconds: Number(e.target.value)}})} /></label>
      <label>Max open positions <input type="number" value={s.risk.max_open_positions} onChange={e => setS({ ...s, risk: { ...s.risk, max_open_positions: Number(e.target.value)}})} /></label>
      <button onClick={() => onSave(s)}>Save</button>
    </div>
  );
}
