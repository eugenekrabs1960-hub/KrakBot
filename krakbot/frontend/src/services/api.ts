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
