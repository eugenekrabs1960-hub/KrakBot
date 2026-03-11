import { useEffect, useMemo, useState } from 'react';
import PageHeader from '../components/PageHeader';
import { getBotState, getEifSummary, getWalletIntelHealth, listStrategies, listTrades } from '../services/api';

function fmtPct(value: number) {
  return `${value.toFixed(1)}%`;
}

export default function Overview() {
  const [data, setData] = useState<any>({});

  useEffect(() => {
    const load = async () => {
      try {
        const [bot, eif, strategies, trades, wallet] = await Promise.all([
          getBotState(),
          getEifSummary().catch(() => null),
          listStrategies(),
          listTrades(25),
          getWalletIntelHealth().catch(() => null),
        ]);
        setData({ bot, eif, strategies, trades, wallet });
      } catch {
        setData({});
      }
    };
    load();
    const t = setInterval(load, 15000);
    return () => clearInterval(t);
  }, []);

  const computed = useMemo(() => {
    const strategies = Array.isArray(data.strategies) ? data.strategies : [];
    const enabledCount = strategies.filter((s: any) => Boolean(s.enabled)).length;
    const tradeItems = data.trades?.items || [];
    const blocked = Number(data.eif?.summary?.blocked_decisions || 0);
    const decisions = Math.max(1, Number(data.eif?.summary?.filter_decisions || 1));
    const skipRatio = (blocked / decisions) * 100;

    return {
      totalStrategies: strategies.length,
      enabledCount,
      tradeCount: tradeItems.length,
      skipRatio,
      botState: data.bot?.state || 'unknown',
      pipeline: data.wallet?.status || 'n/a',
      benchmarkConfidence: Number(data.wallet?.latest_signal?.benchmark_confidence || 0),
    };
  }, [data]);

  const degradedReasons: string[] = [];
  if (!['running', 'paused'].includes(String(computed.botState))) degradedReasons.push('Bot runtime state is not healthy.');
  if (!['ok', 'healthy', 'ready'].includes(String(computed.pipeline).toLowerCase())) degradedReasons.push('Wallet-intel pipeline is degraded or unavailable.');
  if (computed.skipRatio > 70) degradedReasons.push('Skip ratio is unusually high; check filter pressure.');

  return (
    <section>
      <PageHeader title="Overview" subtitle="Portfolio posture, runtime health, and operator-first performance signals." />

      {degradedReasons.length > 0 && (
        <div className="alert degraded" role="status">
          <strong>Degraded state detected</strong>
          <ul>
            {degradedReasons.map((r) => <li key={r}>{r}</li>)}
          </ul>
        </div>
      )}

      <div className="kpi-strip">
        <article className="kpi-hero">
          <div className="kpi-icon">⚙️</div>
          <div>
            <div className="kpi-label">Bot State</div>
            <div className="kpi-value">{computed.botState}</div>
            <div className="kpi-sub">Operator command surface status</div>
          </div>
        </article>

        <article className="kpi-hero">
          <div className="kpi-icon">🧠</div>
          <div>
            <div className="kpi-label">Skip Ratio</div>
            <div className="kpi-value">{fmtPct(computed.skipRatio)}</div>
            <div className="kpi-sub">Blocked vs total filter decisions</div>
          </div>
        </article>

        <article className="kpi-hero">
          <div className="kpi-icon">📈</div>
          <div>
            <div className="kpi-label">Trades (25)</div>
            <div className="kpi-value">{computed.tradeCount}</div>
            <div className="kpi-sub">Recent execution pulse</div>
          </div>
        </article>

        <article className="kpi-hero">
          <div className="kpi-icon">🛰️</div>
          <div>
            <div className="kpi-label">WIB Pipeline</div>
            <div className="kpi-value">{computed.pipeline}</div>
            <div className="kpi-sub">Benchmark confidence {computed.benchmarkConfidence.toFixed(1)}</div>
          </div>
        </article>
      </div>

      <div className="grid" style={{ gridTemplateColumns: '1fr 1fr', marginTop: 12 }}>
        <div className="card glass-card compact">
          <h3 style={{ marginTop: 0 }}>Strategy Coverage</h3>
          <div className="muted">{computed.enabledCount}/{computed.totalStrategies} enabled</div>
        </div>
        <div className="card glass-card compact">
          <h3 style={{ marginTop: 0 }}>Operator Focus</h3>
          <div className="muted">Prioritize degraded components before sending risk-on commands.</div>
        </div>
      </div>
    </section>
  );
}
