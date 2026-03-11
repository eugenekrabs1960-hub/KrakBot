import { useEffect, useMemo, useState } from 'react';
import PageHeader from '../components/PageHeader';
import StatCard from '../components/StatCard';
import {
  getHyperliquidExecutionAccount,
  getHyperliquidExecutionHealth,
  getHyperliquidExecutionPositions,
  getWalletIntelAlignmentSummary,
  getWalletIntelHealth,
} from '../services/api';

export default function Dashboard() {
  const [health, setHealth] = useState<any>(null);
  const [align, setAlign] = useState<any>(null);
  const [hlHealth, setHlHealth] = useState<any>(null);
  const [hlAccount, setHlAccount] = useState<any>(null);
  const [hlPositions, setHlPositions] = useState<any[]>([]);

  useEffect(() => {
    const load = async () => {
      const [h, a, hh, ha, hp] = await Promise.all([
        getWalletIntelHealth().catch(() => null),
        getWalletIntelAlignmentSummary(14).catch(() => null),
        getHyperliquidExecutionHealth().catch(() => null),
        getHyperliquidExecutionAccount().catch(() => null),
        getHyperliquidExecutionPositions().catch(() => null),
      ]);
      setHealth(h);
      setAlign(a);
      setHlHealth(hh?.item || null);
      setHlAccount(ha?.item || null);
      setHlPositions(Array.isArray(hp?.items) ? hp.items : []);
    };
    load();
    const timer = setInterval(load, 30000);
    return () => clearInterval(timer);
  }, []);

  const totalNotional = useMemo(() => {
    return hlPositions.reduce((acc, p) => acc + Math.abs(Number(p.qty || 0) * Number(p.avg_entry_price || 0)), 0);
  }, [hlPositions]);

  return (
    <section>
      <PageHeader title="Benchmark, Wallet Intel & Hyperliquid" subtitle="Cohort quality plus Hyperliquid-native execution/account observability." />
      <div className="grid kpi">
        <StatCard label="Pipeline Status" value={health?.status || 'unknown'} />
        <StatCard label="Provider" value={health?.provider || 'n/a'} />
        <StatCard label="Latest Bias" value={health?.latest_signal?.bias_state || 'n/a'} />
        <StatCard label="Benchmark Confidence" value={Number(health?.latest_signal?.benchmark_confidence || 0).toFixed(1)} />
        <StatCard label="14d Alignment Events" value={align?.total ?? 0} />
      </div>

      <div className="grid" style={{ gridTemplateColumns: '1fr 1fr', marginTop: 12 }}>
        <div className="card glass-card">
          <h3 style={{ marginTop: 0 }}>Hyperliquid Health</h3>
          <div className="muted">Enabled: {String(Boolean(hlHealth?.enabled))}</div>
          <div className="muted">Environment: {hlHealth?.environment || 'n/a'}</div>
          <div className="muted">Auth Configured: {String(Boolean(hlHealth?.auth_configured))}</div>
          <div className="muted">Account Configured: {String(Boolean(hlHealth?.account_configured))}</div>
        </div>

        <div className="card glass-card">
          <h3 style={{ marginTop: 0 }}>Hyperliquid Account</h3>
          <div className="muted">Equity USD: {Number(hlAccount?.equity_usd || 0).toFixed(2)}</div>
          <div className="muted">Available Margin: {Number(hlAccount?.available_margin_usd || 0).toFixed(2)}</div>
          <div className="muted">Maintenance Margin: {Number(hlAccount?.maintenance_margin_usd || 0).toFixed(2)}</div>
          <div className="muted">Open Position Notional: {totalNotional.toFixed(2)}</div>
        </div>
      </div>

      <div className="card table-wrap glass-card" style={{ marginTop: 12 }}>
        <h3 style={{ marginTop: 0 }}>Hyperliquid Positions</h3>
        <table className="responsive-table">
          <thead><tr><th>Market</th><th>Qty</th><th>Entry</th><th>Leverage</th><th>Liq Px</th><th>uPnL</th></tr></thead>
          <tbody>
            {hlPositions.length === 0 ? (
              <tr><td colSpan={6} className="muted">No active Hyperliquid positions.</td></tr>
            ) : hlPositions.map((p, i) => (
              <tr key={`${p.market}-${i}`}>
                <td data-label="Market">{p.market}</td>
                <td data-label="Qty">{Number(p.qty || 0).toFixed(4)}</td>
                <td data-label="Entry">{Number(p.avg_entry_price || 0).toFixed(4)}</td>
                <td data-label="Leverage">{Number(p.leverage || 0).toFixed(2)}x</td>
                <td data-label="Liq Px">{p.liquidation_price ? Number(p.liquidation_price).toFixed(4) : 'n/a'}</td>
                <td data-label="uPnL">{Number(p.unrealized_pnl_usd || 0).toFixed(2)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
