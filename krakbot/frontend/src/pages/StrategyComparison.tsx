import { useEffect, useMemo, useState } from 'react';
import { getEifFilterDecisions, getEifFlags, getEifRegimes, getEifScorecards, getStrategyDetail, getStrategySummary, listStrategies } from '../services/api';

type StrategyRow = {
  strategy_instance_id: string;
  name: string;
  enabled: boolean;
  status: string;
  market: string;
  pnl_usd: number;
  drawdown_pct: number;
  win_rate_pct: number;
  trade_count: number;
  current_position_qty: number;
  equity_usd: number;
};

type WindowLabel = 'rolling_50' | 'baseline';

export default function StrategyComparison() {
  const [rows, setRows] = useState<StrategyRow[]>([]);
  const [selected, setSelected] = useState<any>(null);
  const [windowLabel, setWindowLabel] = useState<WindowLabel>('rolling_50');
  const [scorecards, setScorecards] = useState<any[]>([]);
  const [regimes, setRegimes] = useState<any[]>([]);
  const [decisions, setDecisions] = useState<any[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string>('');
  const [eifEnabled, setEifEnabled] = useState<boolean>(false);
  const [summary, setSummary] = useState<any>(null);

  async function refresh() {
    setLoading(true);
    setError('');
    try {
      const [strategyData, flags, stratSummary] = await Promise.all([listStrategies(), getEifFlags(), getStrategySummary()]);
       const strategyRows = Array.isArray(strategyData) ? strategyData : [];
       setRows(strategyRows);
+      setSummary(stratSummary?.item || null);
      const strategyRows = Array.isArray(strategyData) ? strategyData : [];
      setRows(strategyRows);

      const analyticsEnabled = Boolean(flags?.eif?.analytics?.api?.enabled);
      setEifEnabled(analyticsEnabled);
      if (!analyticsEnabled) {
        setScorecards([]);
        setRegimes([]);
        setDecisions([]);
        return;
      }

      const [sc, rg, fd] = await Promise.all([
        getEifScorecards({ limit: 200 }),
        getEifRegimes({ limit: 200 }),
        getEifFilterDecisions({ limit: 200 }),
      ]);
      setScorecards(sc?.items || []);
      setRegimes(rg?.items || []);
      setDecisions(fd?.items || []);
    } catch (e: any) {
      setError(e?.message || 'failed to load strategy comparison');
      setRows([]);
      setScorecards([]);
      setRegimes([]);
      setDecisions([]);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refresh();
    const timer = setInterval(refresh, 15000);
    return () => clearInterval(timer);
  }, []);

  async function loadDetail(strategyInstanceId: string) {
    try {
      const detail = await getStrategyDetail(strategyInstanceId);
      setSelected(detail.item || null);
    } catch {
      setSelected(null);
    }
  }

  const filteredScorecards = useMemo(
    () => scorecards.filter((s) => (windowLabel === 'baseline' ? s.window_label === 'baseline' : s.window_label !== 'baseline')),
    [scorecards, windowLabel],
  );

  const byMarket = useMemo(() => {
    const bucket: Record<string, number> = {};
    filteredScorecards.forEach((s) => {
      bucket[s.market || 'unknown'] = (bucket[s.market || 'unknown'] || 0) + 1;
    });
    return Object.entries(bucket).sort((a, b) => b[1] - a[1]);
  }, [filteredScorecards]);

  const byRegime = useMemo(() => {
    const bucket: Record<string, number> = {};
    regimes.forEach((r) => {
      const key = `${r.trend || 'unknown'} / ${r.volatility || 'unknown'} / ${r.liquidity || 'unknown'}`;
      bucket[key] = (bucket[key] || 0) + 1;
    });
    return Object.entries(bucket).sort((a, b) => b[1] - a[1]);
  }, [regimes]);

  return (
    <section>
      <h2>Strategy Comparison</h2>
      <p>
        EIF window:
        <select value={windowLabel} onChange={(e) => setWindowLabel(e.target.value as WindowLabel)} style={{ marginLeft: 8 }}>
          <option value="rolling_50">rolling</option>
          <option value="baseline">baseline</option>
        </select>
      </p>

      {loading && <p>Loading strategy/eif data…</p>}
      {!loading && error && <p style={{ color: '#b00020' }}>Error: {error}</p>}
      {!loading && summary && (
        <p>
          Aggregate equity: {Number(summary.aggregate_equity_usd || 0).toFixed(2)} |
          Starting equity: {Number(summary.aggregate_starting_equity_usd || 0).toFixed(2)} |
          Aggregate PnL: {Number(summary.aggregate_pnl_usd || 0).toFixed(4)} |
          Enabled strategies: {summary.enabled_strategies}/{summary.total_strategies}
        </p>
      )}

      {!loading && rows.length === 0 ? (
        <p>No strategy instances yet.</p>
      ) : (
        <ul>
          {rows.map((r) => (
            <li key={r.strategy_instance_id}>
              <button onClick={() => loadDetail(r.strategy_instance_id)} style={{ marginRight: 8 }}>detail</button>
              {r.name} | enabled: {String(r.enabled)} | status: {r.status} | pnl: {r.pnl_usd.toFixed(2)} | dd: {r.drawdown_pct.toFixed(2)}% | win: {r.win_rate_pct.toFixed(1)}% | trades: {r.trade_count} | pos: {r.current_position_qty} | equity: {r.equity_usd.toFixed(2)}
            </li>
          ))}
        </ul>
      )}

      {selected && (
        <p>
          Selected: {selected.strategy_instance_id} | avg entry: {Number(selected.avg_entry_price || 0).toFixed(4)} | realized pnl: {Number(selected.realized_pnl_usd || 0).toFixed(2)}
        </p>
      )}

      {!loading && (
        <>
          {!eifEnabled ? (
            <p>EIF analytics disabled. Enable EIF_ANALYTICS_API_ENABLED for slices/confidence panels.</p>
          ) : (
            <>
              <h3>EIF scorecards ({windowLabel})</h3>
              {filteredScorecards.length === 0 ? (
                <p>No scorecards for selected window.</p>
              ) : (
                <ul>
                  {filteredScorecards.slice(0, 6).map((s, i) => (
                    <li key={`${s.id || i}`}>
                      {s.strategy_instance_id} | {s.market} | n={s.sample_size ?? 0} {Number(s.sample_size || 0) < 20 ? '(exploratory low-n)' : ''} | win={Number(s.win_rate || 0).toFixed(3)} | expectancy={Number(s.expectancy || 0).toFixed(4)}
                    </li>
                  ))}
                </ul>
              )}

              <p>Recent decision sample size: {decisions.length} | confidence: {decisions.length < 20 ? 'low' : decisions.length < 80 ? 'medium' : 'high'}</p>

              <h4>By market</h4>
              {byMarket.length === 0 ? <p>No market slices yet.</p> : <p>{byMarket.map(([m, c]) => `${m}: ${c}`).join(' | ')}</p>}

              <h4>By regime</h4>
              {byRegime.length === 0 ? <p>No regime slices yet.</p> : <p>{byRegime.slice(0, 6).map(([m, c]) => `${m}: ${c}`).join(' | ')}</p>}
            </>
          )}
        </>
      )}
    </section>
  );
}
