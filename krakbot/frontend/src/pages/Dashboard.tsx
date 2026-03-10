import { useEffect, useState } from 'react';
import { getEifFilterDecisions, getEifFlags, getEifRegimes, getEifSummary, getWalletIntelAlignmentSummary, getWalletIntelHealth } from '../services/api';

export default function Dashboard() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [enabled, setEnabled] = useState(false);
  const [summary, setSummary] = useState<any>(null);
  const [regime, setRegime] = useState<any>(null);
  const [reason, setReason] = useState<string>('n/a');
  const [wibSignal, setWibSignal] = useState<any>(null);
  const [alignSummary, setAlignSummary] = useState<any>(null);

  useEffect(() => {
    async function refresh() {
      setLoading(true);
      setError('');
      try {
        const flags = await getEifFlags();
        const ok = Boolean(flags?.eif?.analytics?.api?.enabled);
        setEnabled(ok);
        if (!ok) {
          setSummary(null);
          setRegime(null);
          setReason('n/a');
          return;
        }

        const [sum, regimes, decisions, wib, align] = await Promise.all([
          getEifSummary(),
          getEifRegimes({ limit: 1 }),
          getEifFilterDecisions({ limit: 50 }),
          getWalletIntelHealth(),
          getWalletIntelAlignmentSummary(7),
        ]);
        setSummary(sum?.summary || null);
        setRegime((regimes?.items || [])[0] || null);
        setReason((decisions?.reason_breakdown || [])[0]?.reason_code || 'n/a');
        setWibSignal(wib?.latest_signal || null);
        setAlignSummary(align || null);
      } catch (e: any) {
        setError(e?.message || 'failed to load dashboard');
      } finally {
        setLoading(false);
      }
    }

    refresh();
    const timer = setInterval(refresh, 15000);
    return () => clearInterval(timer);
  }, []);

  return (
    <section>
      <h2>Dashboard</h2>
      <p>Live SOL/USD, bot status, active strategies, PnL, positions, recent trades.</p>
      {loading && <p>Loading EIF summary…</p>}
      {!loading && error && <p style={{ color: '#b00020' }}>Error: {error}</p>}
      {!loading && !enabled && <p>EIF disabled (feature flags off).</p>}
      {!loading && enabled && (
        <ul>
          <li>Current regime: {regime ? `${regime.trend}/${regime.volatility}/${regime.liquidity}` : 'n/a'}</li>
          <li>Skip ratio: {Number(summary?.filter_decisions || 0) > 0 ? (((Number(summary?.blocked_decisions || 0) / Number(summary?.filter_decisions || 1)) * 100).toFixed(1) + '%') : 'n/a'}</li>
          <li>Top reason code: {reason}</li>
          <li>Benchmark bias/confidence: {wibSignal ? `${wibSignal.bias_state} / ${Number(wibSignal.benchmark_confidence || 0).toFixed(1)}` : 'n/a'}</li>
          <li>Benchmark degraded state: {wibSignal?.degraded_state || 'none'}</li>
          <li>7d alignment observations: {alignSummary?.total ?? 'n/a'}</li>
        </ul>
      )}
    </section>
  );
}
