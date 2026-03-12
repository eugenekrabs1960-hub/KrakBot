const API_BASE = '/api';

async function parseJsonOrThrow(res: Response) {
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data?.detail || `Request failed (${res.status})`);
  }
  return data;
}

export async function getHealth() {
  const res = await fetch(`${API_BASE}/health`);
  return parseJsonOrThrow(res);
}

export async function getBotState() {
  const res = await fetch(`${API_BASE}/control/bot`);
  return parseJsonOrThrow(res);
}

export async function sendBotCommand(command: 'start' | 'pause' | 'resume' | 'stop' | 'reload') {
  const res = await fetch(`${API_BASE}/control/bot`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ command }),
  });
  return parseJsonOrThrow(res);
}

export async function getExecutionVenue() {
  const res = await fetch(`${API_BASE}/control/execution/venue`);
  return parseJsonOrThrow(res);
}

export async function setExecutionVenue(defaultVenue: 'paper' | 'hyperliquid') {
  const res = await fetch(`${API_BASE}/control/execution/venue`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ default_venue: defaultVenue }),
  });
  return parseJsonOrThrow(res);
}

export async function getEifFlags() {
  const res = await fetch(`${API_BASE}/control/eif-flags`);
  return parseJsonOrThrow(res);
}

export async function listStrategies() {
  const res = await fetch(`${API_BASE}/strategies`);
  return parseJsonOrThrow(res);
}

export async function getStrategyDetail(strategyInstanceId: string) {
  const res = await fetch(`${API_BASE}/strategies/${strategyInstanceId}`);
  return parseJsonOrThrow(res);
}

export async function getStrategySummary() {
  const res = await fetch(`${API_BASE}/strategies/summary`);
  return parseJsonOrThrow(res);
}

export async function createStrategyInstance(payload: {
  strategy_name: 'trend_following' | 'mean_reversion' | 'breakout';
  market: string;
  instrument_type?: string;
  starting_equity_usd?: number;
  params?: Record<string, any>;
}) {
  const res = await fetch(`${API_BASE}/strategies/instances`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  return parseJsonOrThrow(res);
}

export async function listTrades(limit = 100) {
  const bounded = Math.max(1, Math.min(limit, 200));
  const res = await fetch(`${API_BASE}/trades?limit=${bounded}`);
  return parseJsonOrThrow(res);
}

export async function getEifSummary() {
  const res = await fetch(`${API_BASE}/eif/summary`);
  return parseJsonOrThrow(res);
}

export async function getWalletIntelHealth() {
  const res = await fetch(`${API_BASE}/wallet-intel/health`);
  return parseJsonOrThrow(res);
}

export async function getWalletIntelAlignmentSummary(lookbackDays = 7) {
  const d = Math.max(1, Math.min(90, lookbackDays));
  const res = await fetch(`${API_BASE}/wallet-intel/alignment/summary?lookback_days=${d}`);
  return parseJsonOrThrow(res);
}

export async function getWalletCohortLatest(cohortId = 'top_sol_active_wallets') {
  const res = await fetch(`${API_BASE}/wallet-intel/cohorts/${cohortId}/latest`);
  return parseJsonOrThrow(res);
}

export async function trainBaselineModel(symbol = 'BTC', limit = 50000) {
  const res = await fetch(`${API_BASE}/model-lab/train-baseline?symbol=${encodeURIComponent(symbol)}&limit=${limit}`, { method: 'POST' });
  return parseJsonOrThrow(res);
}

export async function getLatestModel(symbol = 'BTC') {
  const res = await fetch(`${API_BASE}/model-lab/latest-model?symbol=${encodeURIComponent(symbol)}`);
  return parseJsonOrThrow(res);
}

export async function getStrategyBenchmarks(symbol = 'BTC', limit = 50000) {
  const res = await fetch(`${API_BASE}/model-lab/strategy-benchmarks?symbol=${encodeURIComponent(symbol)}&limit=${limit}`);
  return parseJsonOrThrow(res);
}

export async function getModelLabJobHistory(limit = 50) {
  const res = await fetch(`${API_BASE}/model-lab/job-history?limit=${Math.max(1, Math.min(limit, 500))}`);
  return parseJsonOrThrow(res);
}

export async function getActivePaperModel() {
  const res = await fetch(`${API_BASE}/model-lab/active-paper-model`);
  return parseJsonOrThrow(res);
}

export async function getActiveExecutionModel() {
  const res = await fetch(`${API_BASE}/model-lab/active-execution-model`);
  return parseJsonOrThrow(res);
}

export async function setActiveExecutionModel(agentId: string, confirmPhrase = 'SWITCH') {
  const q = new URLSearchParams({ agent_id: agentId, confirm_phrase: confirmPhrase });
  const res = await fetch(`${API_BASE}/model-lab/set-active-execution-model?${q.toString()}`, { method: 'POST' });
  return parseJsonOrThrow(res);
}

export async function promoteModelToPaper(symbol: string, modelPath: string, confirmPhrase = 'PROMOTE') {
  const q = new URLSearchParams({ symbol, model_path: modelPath, confirm_phrase: confirmPhrase });
  const res = await fetch(`${API_BASE}/model-lab/promote-to-paper?${q.toString()}`, { method: 'POST' });
  return parseJsonOrThrow(res);
}

export async function getAgentDecisionPackets(limit = 100, agentId?: string, symbol?: string) {
  const q = new URLSearchParams({ limit: String(limit) });
  if (agentId) q.set('agent_id', agentId);
  if (symbol) q.set('symbol', symbol);
  const res = await fetch(`${API_BASE}/agents/decision-packets?${q.toString()}`);
  return parseJsonOrThrow(res);
}

export async function getJasonState() {
  const res = await fetch(`${API_BASE}/agents/jason/state`);
  return parseJsonOrThrow(res);
}

export async function getJasonTrades(limit = 30) {
  const bounded = Math.max(1, Math.min(limit, 200));
  const res = await fetch(`${API_BASE}/agents/jason/trades?limit=${bounded}`);
  return parseJsonOrThrow(res);
}

export async function getHyperliquidExecutionHealth() {
  const res = await fetch(`${API_BASE}/execution/hyperliquid/health`);
  return parseJsonOrThrow(res);
}

export async function getHyperliquidExecutionAccount() {
  const res = await fetch(`${API_BASE}/execution/hyperliquid/account`);
  return parseJsonOrThrow(res);
}

export async function getHyperliquidExecutionPositions() {
  const res = await fetch(`${API_BASE}/execution/hyperliquid/positions`);
  return parseJsonOrThrow(res);
}

export async function getEifRegimes(params: { market?: string; strategy_instance_id?: string; limit?: number; offset?: number } = {}) {
  const search = new URLSearchParams();
  if (params.market) search.set('market', params.market);
  if (params.strategy_instance_id) search.set('strategy_instance_id', params.strategy_instance_id);
  search.set('limit', String(Math.max(1, Math.min(params.limit ?? 50, 200))));
  search.set('offset', String(Math.max(0, params.offset ?? 0)));
  const res = await fetch(`${API_BASE}/eif/regimes?${search.toString()}`);
  return parseJsonOrThrow(res);
}

export async function getEifFilterDecisions(params: { market?: string; strategy_instance_id?: string; reason_code?: string; limit?: number; offset?: number } = {}) {
  const search = new URLSearchParams();
  if (params.market) search.set('market', params.market);
  if (params.strategy_instance_id) search.set('strategy_instance_id', params.strategy_instance_id);
  if (params.reason_code) search.set('reason_code', params.reason_code);
  search.set('limit', String(Math.max(1, Math.min(params.limit ?? 50, 200))));
  search.set('offset', String(Math.max(0, params.offset ?? 0)));
  const res = await fetch(`${API_BASE}/eif/filter-decisions?${search.toString()}`);
  return parseJsonOrThrow(res);
}

export async function getEifScorecards(params: { market?: string; strategy_instance_id?: string; limit?: number; offset?: number } = {}) {
  const search = new URLSearchParams();
  if (params.market) search.set('market', params.market);
  if (params.strategy_instance_id) search.set('strategy_instance_id', params.strategy_instance_id);
  search.set('limit', String(Math.max(1, Math.min(params.limit ?? 50, 200))));
  search.set('offset', String(Math.max(0, params.offset ?? 0)));
  const res = await fetch(`${API_BASE}/eif/scorecards?${search.toString()}`);
  return parseJsonOrThrow(res);
}

export async function getEifTradeTrace(params: { market?: string; strategy_instance_id?: string; limit?: number; offset?: number } = {}) {
  const search = new URLSearchParams();
  if (params.market) search.set('market', params.market);
  if (params.strategy_instance_id) search.set('strategy_instance_id', params.strategy_instance_id);
  search.set('limit', String(Math.max(1, Math.min(params.limit ?? 50, 200))));
  search.set('offset', String(Math.max(0, params.offset ?? 0)));
  const res = await fetch(`${API_BASE}/eif/trade-trace?${search.toString()}`);
  return parseJsonOrThrow(res);
}


export async function getJasonRiskProfile() {
  const res = await fetch(`${API_BASE}/agents/jason/risk-profile`);
  return parseJsonOrThrow(res);
}

export async function setJasonRiskProfile(profile: 'conservative' | 'balanced' | 'aggressive') {
  const res = await fetch(`${API_BASE}/agents/jason/risk-profile`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ profile }),
  });
  return parseJsonOrThrow(res);
}


export async function getJasonBenchmarkReasoning(limit = 200) {
  const bounded = Math.max(1, Math.min(limit, 2000));
  const res = await fetch(`${API_BASE}/agents/jason/benchmark-reasoning?limit=${bounded}`);
  return parseJsonOrThrow(res);
}


export async function exportJasonBenchmarkReasoningCsv(limit = 5000) {
  const bounded = Math.max(1, Math.min(limit, 50000));
  const res = await fetch(`${API_BASE}/agents/jason/benchmark-reasoning/export-job?limit=${bounded}`, { method: 'POST' });
  return parseJsonOrThrow(res);
}


export async function exportBenchmarkReasoningDataset(agentId = 'jason', limit = 5000) {
  const q = new URLSearchParams({ agent_id: agentId, limit: String(Math.max(1, Math.min(limit, 50000))) });
  const res = await fetch(`${API_BASE}/model-lab/benchmark-reasoning/export-job?${q.toString()}`, { method: 'POST' });
  return parseJsonOrThrow(res);
}

export async function getLastBenchmarkReasoningDataset() {
  const res = await fetch(`${API_BASE}/model-lab/benchmark-reasoning/last-export`);
  return parseJsonOrThrow(res);
}


export async function getLiveTradingGuard() {
  const res = await fetch(`${API_BASE}/control/live-trading`);
  return parseJsonOrThrow(res);
}


export async function getJasonUniverse() {
  const res = await fetch(`${API_BASE}/agents/jason/universe`);
  return parseJsonOrThrow(res);
}

export async function setJasonUniverse(symbols: string[]) {
  const res = await fetch(`${API_BASE}/agents/jason/universe`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ symbols }),
  });
  return parseJsonOrThrow(res);
}
