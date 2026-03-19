import React from 'react';
import ModeBadge from '../components/ModeBadge';

export default function Overview({ data, onRun }: any) {
  return <div>
    <h2>Overview</h2>
    <ModeBadge mode={data?.mode?.execution_mode || 'paper'} armed={!!data?.mode?.live_armed} />
    <div style={{ marginTop: 10 }}><button onClick={onRun}>Run Decision Cycle</button></div>
    <pre>{JSON.stringify(data, null, 2)}</pre>
  </div>
}
