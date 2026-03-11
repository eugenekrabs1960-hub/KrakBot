import { useEffect, useState } from 'react';
import PageHeader from '../components/PageHeader';
import StatCard from '../components/StatCard';
import { getBotState, getEifSummary, getWalletIntelHealth, listStrategies, listTrades } from '../services/api';

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

  return (
    <section>
      <PageHeader title="Overview" subtitle="Portfolio posture, runtime status, and live trading pulse." />
      <div className="grid kpi">
        <StatCard label="Bot State" value={data.bot?.state || 'unknown'} />
        <StatCard label="Strategies" value={Array.isArray(data.strategies) ? data.strategies.length : 0} />
        <StatCard label="Trades (25)" value={data.trades?.items?.length || 0} />
        <StatCard label="Skip Ratio" value={`${(((data.eif?.summary?.blocked_decisions || 0) / Math.max(1, data.eif?.summary?.filter_decisions || 1)) * 100).toFixed(1)}%`} />
        <StatCard label="WIB Pipeline" value={data.wallet?.status || 'n/a'} />
      </div>
    </section>
  );
}
