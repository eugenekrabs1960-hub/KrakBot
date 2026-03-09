const API_BASE = '/api';

export async function getHealth() {
  const res = await fetch(`${API_BASE}/health`);
  return res.json();
}

export async function listStrategies() {
  const res = await fetch(`${API_BASE}/strategies`);
  return res.json();
}

export async function listTrades(limit = 100) {
  const res = await fetch(`${API_BASE}/trades?limit=${limit}`);
  return res.json();
}
