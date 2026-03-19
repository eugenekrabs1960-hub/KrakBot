const API = '/api';

export const getOverview = () => fetch(`${API}/overview`).then(r => r.json());
export const getCandidates = () => fetch(`${API}/candidates`).then(r => r.json());
export const getPositions = () => fetch(`${API}/positions`).then(r => r.json());
export const getDecisions = () => fetch(`${API}/decisions/recent`).then(r => r.json());
export const runCycle = () => fetch(`${API}/decisions/run-cycle`, { method: 'POST' }).then(r => r.json());
export const getSettings = () => fetch(`${API}/settings`).then(r => r.json());
export const saveSettings = (body: any) =>
  fetch(`${API}/settings`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(body),
  }).then(r => r.json());

// phase 2d observability
export const getLoopsStatus = () => fetch(`${API}/loops/status`).then(r => r.json());
export const getLoopsHistory = (limit = 20) => fetch(`${API}/loops/history?limit=${limit}`).then(r => r.json());
export const getReconciliationHistory = (limit = 20) => fetch(`${API}/reconciliation/history?limit=${limit}`).then(r => r.json());
export const getRelayHistory = (limit = 20) => fetch(`${API}/execution/relay/history?limit=${limit}`).then(r => r.json());
