import React from 'react';
import ModeBadge from '../components/ModeBadge';

function Box({ title, children }: any) {
  return (
    <div style={{ border: '1px solid #333', borderRadius: 8, padding: 10, marginTop: 12 }}>
      <h3 style={{ marginTop: 0 }}>{title}</h3>
      {children}
    </div>
  );
}

export default function Overview({ data, modelHealth, loopsStatus, loopsHistory, reconHistory, relayHistory, walletSummary, onRun }: any) {
  return (
    <div>
      <h2>Overview</h2>
      <ModeBadge mode={data?.mode?.execution_mode || 'paper'} armed={!!data?.mode?.live_armed} />
      <div style={{ marginTop: 6 }}>
        Trading enabled: <b>{String(data?.mode?.trading_enabled ?? true)}</b> | Live armed: <b>{String(data?.mode?.live_armed ?? false)}</b>
      </div>
      <div style={{ marginTop: 10 }}><button onClick={onRun}>Run Decision Cycle</button></div>

      <Box title="Local Model Runtime">
        <pre>{JSON.stringify(modelHealth || {}, null, 2)}</pre>
      </Box>

      <Box title="Wallet Intelligence (Read-Only)">
        <pre style={{ maxHeight: 180, overflow: 'auto' }}>{JSON.stringify(walletSummary?.items || data?.wallet_summaries || [], null, 2)}</pre>
      </Box>

      <Box title="Loop Health / History">
        <div style={{ marginBottom: 8 }}>
          Last feature run: {loopsStatus?.last_feature_run_at || '-'}<br/>
          Last decision run: {loopsStatus?.last_decision_run_at || '-'}<br/>
          Last error: {loopsStatus?.last_error || 'none'}
        </div>
        <pre style={{ maxHeight: 180, overflow: 'auto' }}>{JSON.stringify(loopsHistory?.items || [], null, 2)}</pre>
      </Box>

      <Box title="Reconciliation History / Drift Alerts">
        <pre style={{ maxHeight: 180, overflow: 'auto' }}>{JSON.stringify(reconHistory?.items || [], null, 2)}</pre>
      </Box>

      <Box title="Live Relay / Idempotency Request History">
        <pre style={{ maxHeight: 180, overflow: 'auto' }}>{JSON.stringify(relayHistory?.items || [], null, 2)}</pre>
      </Box>
    </div>
  );
}
