export const fmtNum = (v: any, digits = 3) => {
  const n = Number(v);
  if (!Number.isFinite(n)) return '-';
  return n.toFixed(digits);
};

export const fmtUsd = (v: any) => {
  const n = Number(v);
  if (!Number.isFinite(n)) return '-';
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 2, minimumFractionDigits: 2 }).format(n);
};

export const fmtPct = (v: any) => {
  const n = Number(v);
  if (!Number.isFinite(n)) return '-';
  return `${(n * 100).toFixed(2)}%`;
};

export const fmtTsLA = (v: any) => {
  if (!v) return '-';
  const d = new Date(v);
  if (Number.isNaN(d.getTime())) return String(v);
  return new Intl.DateTimeFormat('en-US', {
    month: 'short', day: 'numeric', year: 'numeric',
    hour: 'numeric', minute: '2-digit',
    timeZone: 'America/Los_Angeles',
    timeZoneName: 'short',
  }).format(d);
};

export const pnlClass = (v: any) => {
  const n = Number(v);
  if (!Number.isFinite(n)) return 'neutral';
  if (n > 0) return 'pos';
  if (n < 0) return 'neg';
  return 'neutral';
};
