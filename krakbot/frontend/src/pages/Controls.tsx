import { useEffect, useState } from 'react';
import PageHeader from '../components/PageHeader';
import Badge from '../components/Badge';
import { getBotState, sendBotCommand } from '../services/api';

const commands = ['start', 'pause', 'resume', 'reload', 'stop'] as const;

export default function Controls() {
  const [state, setState] = useState('loading');
  const [armed, setArmed] = useState(false);
  const [confirm, setConfirm] = useState('');

  useEffect(() => {
    getBotState().then((d) => setState(d.state || 'unknown')).catch(() => setState('error'));
  }, []);

  async function run(cmd: (typeof commands)[number]) {
    const dangerous = cmd === 'stop';
    if (dangerous && (!armed || confirm !== 'STOP')) return;
    const data = await sendBotCommand(cmd);
    setState(data.state || data.detail || 'unknown');
    setConfirm('');
  }

  return (
    <section>
      <PageHeader title="Controls & Safety" subtitle="Command center with operator safeguards for risky actions." />
      <div className="card">
        <p>Runtime State: <Badge tone={state === 'running' ? 'good' : state === 'paused' ? 'warn' : 'info'}>{state}</Badge></p>
        <div className="toolbar">
          {commands.map((c) => <button key={c} className={`btn ${c === 'stop' ? 'danger' : ''}`} onClick={() => run(c)}>{c}</button>)}
        </div>
        <hr style={{ borderColor: 'var(--border)' }} />
        <label style={{ display: 'block', marginBottom: 8 }}>
          <input type="checkbox" checked={armed} onChange={(e) => setArmed(e.target.checked)} /> Arm dangerous actions
        </label>
        <input placeholder="Type STOP to allow stop command" value={confirm} onChange={(e) => setConfirm(e.target.value)} />
      </div>
    </section>
  );
}
