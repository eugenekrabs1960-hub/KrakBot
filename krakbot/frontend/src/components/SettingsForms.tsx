import React, { useEffect, useState } from 'react';

function Section({ title, children, danger = false }: any) {
  return (
    <div className="card" style={{ borderColor: danger ? '#8a2c2c' : undefined }}>
      <h3 style={{ marginTop: 0 }}>{title}</h3>
      <div className="grid" style={{ gap: 8 }}>{children}</div>
    </div>
  );
}

export default function SettingsForms({ initial, onSave }: any) {
  const [s, setS] = useState(initial);
  useEffect(() => setS(initial), [initial]);
  if (!s) return null;

  return (
    <div className="grid" style={{ gap: 12 }}>
      <Section title="Mode & Safety" danger>
        <label>Execution Mode
          <select value={s.mode.execution_mode} onChange={e => setS({ ...s, mode: { ...s.mode, execution_mode: e.target.value } })}>
            <option value="paper">paper</option>
            <option value="live_hyperliquid">live_hyperliquid</option>
          </select>
        </label>
        <label>Trading Enabled <input type="checkbox" checked={!!s.mode.trading_enabled} onChange={e => setS({ ...s, mode: { ...s.mode, trading_enabled: e.target.checked } })} /></label>
        <label>Live Armed (dangerous) <input type="checkbox" checked={!!s.mode.live_armed} onChange={e => setS({ ...s, mode: { ...s.mode, live_armed: e.target.checked } })} /></label>
        <label>Emergency Stop <input type="checkbox" checked={!!s.mode.emergency_stop} onChange={e => setS({ ...s, mode: { ...s.mode, emergency_stop: e.target.checked } })} /></label>
      </Section>

      <Section title="Universe">
        <label>Tracked Coins (comma)
          <input value={s.universe.tracked_coins.join(',')} onChange={e => setS({ ...s, universe: { ...s.universe, tracked_coins: e.target.value.split(',').map((x:string)=>x.trim()).filter(Boolean)}})} />
        </label>
        <label>Max candidates per cycle
          <input type="number" value={s.universe.max_candidates_per_cycle} onChange={e => setS({ ...s, universe: { ...s.universe, max_candidates_per_cycle: Number(e.target.value)}})} />
        </label>
      </Section>

      <Section title="Loop Cadence">
        <label>Feature refresh seconds
          <input type="number" value={s.loop.feature_refresh_seconds} onChange={e => setS({ ...s, loop: { ...s.loop, feature_refresh_seconds: Number(e.target.value)}})} />
        </label>
        <label>Decision cycle seconds
          <input type="number" value={s.loop.decision_cycle_seconds} onChange={e => setS({ ...s, loop: { ...s.loop, decision_cycle_seconds: Number(e.target.value)}})} />
        </label>
        <label>Primary horizon
          <input value={s.loop.primary_horizon} onChange={e => setS({ ...s, loop: { ...s.loop, primary_horizon: e.target.value}})} />
        </label>
      </Section>

      <Section title="Model Runtime">
        <label>Model Name
          <input value={s.model.model_name} onChange={e => setS({ ...s, model: { ...s.model, model_name: e.target.value } })} />
        </label>
        <label>Context Limit
          <input type="number" value={s.model.context_limit} onChange={e => setS({ ...s, model: { ...s.model, context_limit: Number(e.target.value)} })} />
        </label>
        <label>Max output tokens
          <input type="number" value={s.model.max_output_tokens} onChange={e => setS({ ...s, model: { ...s.model, max_output_tokens: Number(e.target.value)} })} />
        </label>
        <label>Temperature
          <input type="number" step="0.01" value={s.model.temperature} onChange={e => setS({ ...s, model: { ...s.model, temperature: Number(e.target.value)} })} />
        </label>
      </Section>

      <Section title="Risk Controls" danger>
        <label>Max open positions
          <input type="number" value={s.risk.max_open_positions} onChange={e => setS({ ...s, risk: { ...s.risk, max_open_positions: Number(e.target.value)}})} />
        </label>
        <label>Max notional per trade
          <input type="number" value={s.risk.max_notional_per_trade} onChange={e => setS({ ...s, risk: { ...s.risk, max_notional_per_trade: Number(e.target.value)}})} />
        </label>
        <label>Max total notional
          <input type="number" value={s.risk.max_total_notional} onChange={e => setS({ ...s, risk: { ...s.risk, max_total_notional: Number(e.target.value)}})} />
        </label>
        <label>Leverage cap
          <input type="number" step="0.1" value={s.risk.leverage_cap} onChange={e => setS({ ...s, risk: { ...s.risk, leverage_cap: Number(e.target.value)}})} />
        </label>
        <label>Allow Long <input type="checkbox" checked={!!s.risk.allow_long} onChange={e => setS({ ...s, risk: { ...s.risk, allow_long: e.target.checked } })} /></label>
        <label>Allow Short <input type="checkbox" checked={!!s.risk.allow_short} onChange={e => setS({ ...s, risk: { ...s.risk, allow_short: e.target.checked } })} /></label>
      </Section>

      <Section title="Experiments (Read-Only context toggles where available)">
        <div className="muted">No experimental settings exposed in this UI yet. Wallet/news/social remain non-decision-impact unless explicitly integrated in future phases.</div>
      </Section>

      <div>
        <button className="btn" onClick={() => onSave(s)}>Save Settings</button>
      </div>
    </div>
  );
}
