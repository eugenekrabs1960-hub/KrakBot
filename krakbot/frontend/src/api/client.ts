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

export const getWalletSummary = () => fetch(`${API}/wallets/summary`).then(r => r.json());

export const getModelHealth = () => fetch(`${API}/model/health`).then(r => r.json());

export const runExperiment = (body: any) => fetch(`${API}/experiments/run`, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(body) }).then(r => r.json());
export const getExperimentRuns = (limit = 20) => fetch(`${API}/experiments/runs?limit=${limit}`).then(r => r.json());

export const runAutonomyStage1 = (cycles = 8) => fetch(`${API}/autonomy/stage1/run-once?cycles=${cycles}`, { method: 'POST' }).then(r => r.json());
export const getAutonomyStage1Recent = (limit = 10) => fetch(`${API}/autonomy/stage1/recent?limit=${limit}`).then(r => r.json());

export const getTrades = (limit = 50) => fetch(`${API}/trades?limit=${limit}`).then(r => r.json());
