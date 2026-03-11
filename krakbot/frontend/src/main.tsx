import React, { useMemo, useState } from 'react';
import ReactDOM from 'react-dom/client';

import AppShell from './components/AppShell';
import Overview from './pages/Overview';
import Dashboard from './pages/Dashboard';
import StrategyComparison from './pages/StrategyComparison';
import StrategyDetail from './pages/StrategyDetail';
import TradeHistory from './pages/TradeHistory';
import MarketData from './pages/MarketData';
import Controls from './pages/Controls';
import MarketRegistry from './pages/MarketRegistry';
import ModelLab from './pages/ModelLab';
import ModelArena from './pages/ModelArena';
import './styles/tokens.css';
import './styles/app.css';

function App() {
  const nav = useMemo(
    () => [
      { id: 'overview', label: 'Overview' },
      { id: 'comparison', label: 'Strategy Comparison' },
      { id: 'strategy', label: 'Strategy Detail' },
      { id: 'trades', label: 'Trades + Trace' },
      { id: 'market', label: 'Market Detail' },
      { id: 'registry', label: 'Market Registry' },
      { id: 'wallet', label: 'Benchmark & Wallet Intel' },
      { id: 'model-lab', label: 'Model Lab' },
      { id: 'model-arena', label: 'Model Arena' },
      { id: 'controls', label: 'Controls & Safety' },
    ],
    [],
  );
  const [active, setActive] = useState('overview');

  return (
    <AppShell nav={nav} active={active} onChange={setActive}>
      {active === 'overview' && <Overview />}
      {active === 'comparison' && <StrategyComparison />}
      {active === 'strategy' && <StrategyDetail />}
      {active === 'trades' && <TradeHistory />}
      {active === 'market' && <MarketData />}
      {active === 'registry' && <MarketRegistry />}
      {active === 'wallet' && <Dashboard />}
      {active === 'model-lab' && <ModelLab />}
      {active === 'model-arena' && <ModelArena />}
      {active === 'controls' && <Controls />}
    </AppShell>
  );
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
