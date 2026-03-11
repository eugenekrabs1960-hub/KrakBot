import { useEffect, useState } from 'react';
import PageHeader from '../components/PageHeader';
import StatCard from '../components/StatCard';
import { getWalletIntelAlignmentSummary, getWalletIntelHealth } from '../services/api';

export default function Dashboard() {
  const [health, setHealth] = useState<any>(null);
  const [align, setAlign] = useState<any>(null);

  useEffect(() => {
    const load = async () => {
      const [h, a] = await Promise.all([
        getWalletIntelHealth().catch(() => null),
        getWalletIntelAlignmentSummary(14).catch(() => null),
      ]);
      setHealth(h);
      setAlign(a);
    };
    load();
    const timer = setInterval(load, 30000);
    return () => clearInterval(timer);
  }, []);

  return (
    <section>
      <PageHeader title="Benchmark & Wallet Intel" subtitle="Cohort quality, benchmark confidence, and strategy alignment signals." />
      <div className="grid kpi">
        <StatCard label="Pipeline Status" value={health?.status || 'unknown'} />
        <StatCard label="Provider" value={health?.provider || 'n/a'} />
        <StatCard label="Latest Bias" value={health?.latest_signal?.bias_state || 'n/a'} />
        <StatCard label="Benchmark Confidence" value={Number(health?.latest_signal?.benchmark_confidence || 0).toFixed(1)} />
        <StatCard label="14d Alignment Events" value={align?.total ?? 0} />
      </div>
    </section>
  );
}
