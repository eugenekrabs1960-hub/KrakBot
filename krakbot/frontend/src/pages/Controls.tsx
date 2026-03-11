import { useEffect, useState } from 'react';
import PageHeader from '../components/PageHeader';
import Badge from '../components/Badge';
import { getBotState, sendBotCommand } from '../services/api';

const commands = ['start', 'pause', 'resume', 'reload', 'stop'] as const;

export default function Controls() {
  const [state, setState] = useState('loading');
  const [armed, setArmed] = useState(false);
  const [confirm, setConfirm] = useState('');
  const [busy, setBusy] = useState<string | null>(null);

  useEffect(() => {
    getBotState().then((d) => setState(d.state || 'unknown')).catch(() => setState('error'));
  }, []);

  async function run(cmd: (typeof commands)[number]) {
    const dangerous = cmd === 'stop';
    if (dangerous && (!armed || confirm !== 'STOP')) return;
    setBusy(cmd);
    try {
      const data = await sendBotCommand(cmd);
      setState(data.state || data.detail || 'unknown');
      setConfirm('');
      if (dangerous) setArmed(false);
    } finally {
      setBusy(null);
    }
  }

  return (
    <section>
      <PageHeader title="Controls & Safety" subtitle="Consistent, safer operator actions with explicit stop protection and command feedback." />
      <div className="card glass-card">
        <p>Runtime State: <Badge tone={state === 'running' ? 'good' : state === 'paused' ? 'warn' : 'info'}>{state}</Badge></p>
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
      </div>
    </section>
  );
}
