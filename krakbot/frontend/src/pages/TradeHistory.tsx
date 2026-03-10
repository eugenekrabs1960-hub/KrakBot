import { useEffect, useMemo, useState } from 'react';
import { getEifFilterDecisions, getEifFlags, getEifTradeTrace, listTrades } from '../services/api';

type Trade = {
  strategy_instance_id: string;
  side: string;
  qty: number;
  entry_price: number;
  realized_pnl_usd?: number;
  ts: string;
  market?: string;
};

export default function TradeHistory() {
  const [trades, setTrades] = useState<Trade[]>([]);
  const [decisionItems, setDecisionItems] = useState<any[]>([]);
  const [traceItems, setTraceItems] = useState<any[]>([]);
  const [eifEnabled, setEifEnabled] = useState<boolean>(false);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string>('');

  async function refresh() {
    setLoading(true);
    setError('');
    try {
      const [tradeData, flags] = await Promise.all([listTrades(25), getEifFlags()]);
      setTrades(tradeData.items || []);

      const analyticsEnabled = Boolean(flags?.eif?.analytics?.api?.enabled);
      setEifEnabled(analyticsEnabled);
      if (!analyticsEnabled) {
        setDecisionItems([]);
        setTraceItems([]);
        return;
      }

      const [decisions, trace] = await Promise.all([
        getEifFilterDecisions({ limit: 40 }),
        getEifTradeTrace({ limit: 40 }),
      ]);
      setDecisionItems(decisions?.items || []);
      setTraceItems(trace?.items || []);
    } catch (e: any) {
      setError(e?.message || 'failed to load trade history');
      setTrades([]);
      setDecisionItems([]);
      setTraceItems([]);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refresh();
    const timer = setInterval(refresh, 15000);
    return () => clearInterval(timer);
  }, []);

  const topTraces = useMemo(() => decisionItems.slice(0, 10), [decisionItems]);

  return (
    <section>
      <h2>Trade History</h2>
      {loading && <p>Loading trades/trace…</p>}
      {!loading && error && <p style={{ color: '#b00020' }}>Error: {error}</p>}

      {!loading && trades.length === 0 ? (
        <p>No trades yet.</p>
      ) : (
        <ul>
          {trades.map((t, i) => (
            <li key={`${t.strategy_instance_id}-${t.ts}-${i}`}>
              {t.strategy_instance_id} | {t.side} {t.qty} @ {Number(t.entry_price).toFixed(4)} | pnl: {Number(t.realized_pnl_usd || 0).toFixed(2)} | ts: {t.ts}
            </li>
          ))}
        </ul>
      )}

      {!loading && !eifEnabled && <p>EIF analytics disabled. Decision trace unavailable.</p>}

      {!loading && eifEnabled && (
        <>
          <h3>Decision Trace (recent allow/skip chain)</h3>
          {topTraces.length === 0 ? (
            <p>No decision trace events yet.</p>
          ) : (
            <ul>
              {topTraces.map((d) => (
                <li key={d.id}>
                  {d.strategy_instance_id} | {d.market} | {d.allowed ? 'ALLOW' : 'SKIP'} ({d.reason_code}) | stage={d.precedence_stage || 'n/a'} | regime_snapshot={d.regime_snapshot_id || 'n/a'}
                  <br />
                  trace: {Array.isArray(d.trace) ? d.trace.join(' > ') : d.trace ? JSON.stringify(d.trace) : 'n/a'}
                </li>
              ))}
            </ul>
          )}

          <h4>Regime snapshot context from trade trace</h4>
          {traceItems.length === 0 ? (
            <p>No trade trace context yet.</p>
          ) : (
            <ul>
              {traceItems.slice(0, 8).map((e) => (
                <li key={e.id}>
                  {e.strategy_instance_id} | {e.market} | {e.event_type} | ts: {e.ts}
                  <br />
                  regime: {e.context?.regime ? JSON.stringify(e.context.regime) : 'n/a'}
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </section>
  );
}
