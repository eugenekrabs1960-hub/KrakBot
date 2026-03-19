import React from 'react';
export default function ModeBadge({ mode, armed }: { mode: string; armed: boolean }) {
  const color = mode === 'paper' ? '#2ea043' : (armed ? '#d29922' : '#f85149');
  return <span style={{ padding: '4px 8px', borderRadius: 8, background: color, color: 'white' }}>{mode} {mode==='live_hyperliquid' ? (armed ? 'ARMED' : 'DISARMED') : ''}</span>
}
