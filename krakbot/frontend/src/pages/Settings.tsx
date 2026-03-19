import React from 'react';
import SettingsForms from '../components/SettingsForms';

export default function Settings({ data, onSave }: any) {
  return (
    <div>
      <h2>Settings Console</h2>
      <p className="muted">Adjust runtime behavior by group. Safety-critical controls are highlighted.</p>
      <SettingsForms initial={data} onSave={onSave} />
    </div>
  );
}
