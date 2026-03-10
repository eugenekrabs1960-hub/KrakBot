import { useEffect, useMemo, useState } from 'react';
import { getBotState, getEifFilterDecisions, getEifFlags, getEifSummary, sendBotCommand } from '../services/api';

const commands = ['start', 'pause', 'resume', 'stop', 'reload'] as const;

export default function Controls() {
  const [state, setState] = useState<string>('loading...');
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string>('');
  const [eifEnabled, setEifEnabled] = useState<boolean>(false);
  const [summary, setSummary] = useState<any>(null);
  const [decisions, setDecisions] = useState<any[]>([]);

  async function refreshState() {
    setLoading(true);
    setError('');
    try {
      const [bot, flags] = await Promise.all([getBotState(), getEifFlags()]);
      setState(bot.state || 'unknown');
      const analyticsEnabled = Boolean(flags?.eif?.analytics?.api?.enabled);
      setEifEnabled(analyticsEnabled);
      if (!analyticsEnabled) {
        setSummary(null);
        setDecisions([]);
        return;
      }
      const [sum, dec] = await Promise.all([getEifSummary(), getEifFilterDecisions({ limit: 100 })]);
      setSummary(sum);
      setDecisions(dec?.items || []);
    } catch (e: any) {
      setError(e?.message || 'failed to load controls');
      setState('error');
      setSummary(null);
      setDecisions([]);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refreshState();
    const timer = setInterval(refreshState, 12000);
    return () => clearInterval(timer);
  }, []);

  async function send(command: (typeof commands)[number]) {
    const data = await sendBotCommand(command);
    setState(data.state || data.detail || 'error');
  }

  const summaryStats = useMemo(() => {
    const blocked = decisions.filter((d) => d.allowed === false).length;
    const total = decisions.length;
    const skipRatio = total === 0 ? 0 : blocked / total;
    const reasonCounts: Record<string, number> = {};
    decisions.forEach((d) => {
      const key = d.reason_code || 'unknown';
      reasonCounts[key] = (reasonCounts[key] || 0) + 1;
    });
    const topReasons = Object.entries(reasonCounts).sort((a, b) => b[1] - a[1]).slice(0, 3);
    const scorecards = Number(summary?.summary?.scorecard_snapshots || 0);
    const expectedDelta = total === 0 ? 0 : (Number(summary?.summary?.allowed_decisions || 0) - blocked) / total;
    return { skipRatio, topReasons, scorecards, expectedDelta };
  }, [decisions, summary]);

  return (
    <section>
      <h2>Controls</h2>
      {loading && <p>Loading controls…</p>}
      {!loading && error && <p style={{ color: '#b00020' }}>Error: {error}</p>}
      <p>Bot state: {state}</p>
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        {commands.map((cmd) => (
          <button key={cmd} onClick={() => send(cmd)}>{cmd}</button>
        ))}
      </div>

      <h3>EIF Operator Summary</h3>
      {!eifEnabled ? (
        <p>EIF analytics disabled. Summary cards hidden until EIF_ANALYTICS_API_ENABLED=true.</p>
      ) : (
        <ul>
          <li>Current regime snapshot count: {summary?.summary?.regime_snapshots ?? 0}</li>
          <li>Skip ratio (recent window): {(summaryStats.skipRatio * 100).toFixed(1)}%</li>
          <li>Top reason codes: {summaryStats.topReasons.length === 0 ? 'n/a' : summaryStats.topReasons.map(([k, v]) => `${k} (${v})`).join(', ')}</li>
          <li>Recent expectancy delta (proxy): {summaryStats.expectedDelta.toFixed(3)}</li>
          <li>Scorecard snapshots: {summaryStats.scorecards}</li>
        </ul>
      )}
    </section>
  );
}
