import { useEffect, useState } from 'react';
import PageHeader from '../components/PageHeader';
import Badge from '../components/Badge';
import { getBotState, getExecutionVenue, sendBotCommand, setExecutionVenue } from '../services/api';

const commands = ['start', 'pause', 'resume', 'reload', 'stop'] as const;

export default function Controls() {
  const [state, setState] = useState('loading');
  const [armed, setArmed] = useState(false);
  const [confirm, setConfirm] = useState('');
  const [busy, setBusy] = useState<string | null>(null);
  const [defaultVenue, setDefaultVenue] = useState<'paper' | 'hyperliquid'>('paper');
  const [venueMsg, setVenueMsg] = useState('');
  const [cmdMsg, setCmdMsg] = useState('');

  useEffect(() => {
    getBotState().then((d) => setState(d.state || 'unknown')).catch(() => setState('error'));
    getExecutionVenue().then((d) => setDefaultVenue((d?.default_venue || 'paper') as 'paper' | 'hyperliquid')).catch(() => setDefaultVenue('paper'));
  }, []);

  async function run(cmd: (typeof commands)[number]) {
    const dangerous = cmd === 'stop';
    if (dangerous && (!armed || confirm !== 'STOP')) return;
    setBusy(cmd);
    setCmdMsg('');
    try {
      const data = await sendBotCommand(cmd);
      setState(data.state || data.detail || 'unknown');
      setCmdMsg(`Command '${cmd}' accepted.`);
      setConfirm('');
      if (dangerous) setArmed(false);
    } catch (err: any) {
      setCmdMsg(err?.message || `Command '${cmd}' failed.`);
    } finally {
      setBusy(null);
    }
  }

  async function saveVenue(v: 'paper' | 'hyperliquid') {
    setVenueMsg('');
    try {
      const out = await setExecutionVenue(v);
      setDefaultVenue((out?.default_venue || v) as 'paper' | 'hyperliquid');
      setVenueMsg('Default execution venue updated.');
    } catch (err: any) {
      setVenueMsg(err?.message || 'Failed to update venue.');
    }
  }

  return (
    <section>
      <PageHeader title="Controls & Safety" subtitle="Consistent, safer operator actions with explicit stop protection and command feedback." />
      <div className="card glass-card compact arena-active-banner" style={{ marginBottom: 12 }}>
        <strong>Runtime State:</strong> <Badge tone={state === 'running' ? 'good' : state === 'paused' ? 'warn' : 'info'}>{state}</Badge>
      </div>

      <div className="card glass-card">
        <h3 style={{ marginTop: 0 }}>Command Console</h3>
        <div className="toolbar quick-controls-row">
          {commands.map((c) => {
            const dangerous = c === 'stop';
            const disabled = Boolean(busy) || (dangerous && (!armed || confirm !== 'STOP'));
            return (
              <button key={c} className={`btn ${dangerous ? 'danger' : ''}`} disabled={disabled} onClick={() => run(c)}>
                {busy === c ? 'Running…' : c}
              </button>
            );
          })}
        </div>
        <hr style={{ borderColor: 'var(--border)' }} />
        <label style={{ display: 'block', marginBottom: 8 }}>
          <input type="checkbox" checked={armed} onChange={(e) => setArmed(e.target.checked)} /> Arm dangerous actions
        </label>
        <input placeholder="Type STOP to allow stop command" value={confirm} onChange={(e) => setConfirm(e.target.value)} />
        <p className="muted" style={{ marginBottom: 0 }}>Safe actions run immediately. Stop requires explicit arm + STOP confirmation.</p>
        {cmdMsg ? <p className="muted" style={{ marginBottom: 0 }}>{cmdMsg}</p> : null}
      </div>

      <div className="card glass-card" style={{ marginTop: 12 }}>
        <h3 style={{ marginTop: 0 }}>Venue Execution Routing</h3>
        <p className="muted">Default venue for operator paper-order flow. Hyperliquid routing remains guarded by testnet safety checks.</p>
        <div className="toolbar">
          <button className={`btn ${defaultVenue === 'paper' ? 'active' : ''}`} onClick={() => saveVenue('paper')}>Use Paper (Freqtrade path)</button>
          <button className={`btn ${defaultVenue === 'hyperliquid' ? 'active' : ''}`} onClick={() => saveVenue('hyperliquid')}>Use Hyperliquid</button>
          <Badge tone={defaultVenue === 'paper' ? 'info' : 'warn'}>Current: {defaultVenue}</Badge>
        </div>
        <p className="muted" style={{ marginBottom: 0 }}>If Hyperliquid environment is not testnet, execution requests will be blocked with an explicit safety error.</p>
        {venueMsg && <p className="muted" style={{ marginBottom: 0 }}>{venueMsg}</p>}
      </div>
    </section>
  );
}
