import React from 'react';
import ReactDOM from 'react-dom/client';

import Dashboard from './pages/Dashboard';
import StrategyComparison from './pages/StrategyComparison';
import TradeHistory from './pages/TradeHistory';
import MarketData from './pages/MarketData';
import Controls from './pages/Controls';

function App() {
  return (
    <main style={{ fontFamily: 'sans-serif', margin: '1.2rem' }}>
      <h1>Krakbot MVP UI Scaffold</h1>
      <Dashboard />
      <StrategyComparison />
      <TradeHistory />
      <MarketData />
      <Controls />
    </main>
  );
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
