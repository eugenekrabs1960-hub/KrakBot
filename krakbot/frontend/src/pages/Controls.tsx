import { useState } from 'react';

const commands = ['start', 'pause', 'resume', 'stop', 'reload'] as const;

export default function Controls() {
  const [state, setState] = useState<string>('unknown');

  async function send(command: (typeof commands)[number]) {
    const res = await fetch('/api/control/bot', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ command }),
    });
    const data = await res.json();
    setState(data.state || data.detail || 'error');
  }

  return (
    <section>
      <h2>Controls</h2>
      <p>Bot state: {state}</p>
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        {commands.map((cmd) => (
          <button key={cmd} onClick={() => send(cmd)}>{cmd}</button>
        ))}
      </div>
    </section>
  );
}
