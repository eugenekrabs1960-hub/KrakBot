import React, { useEffect, useState } from 'react';
import ReactDOM from 'react-dom/client';
import Layout from './components/Layout';
import Overview from './pages/Overview';
import Candidates from './pages/Candidates';
import Positions from './pages/Positions';
import Decisions from './pages/Decisions';
import Settings from './pages/Settings';
import Experiments from './pages/Experiments';
import {
  getOverview,
  getCandidates,
  getPositions,
  getDecisions,
  getSettings,
  saveSettings,
  runCycle,
  getLoopsStatus,
  getLoopsHistory,
  getReconciliationHistory,
  getRelayHistory,
  getWalletSummary,
  getModelHealth,
  runExperiment,
  getExperimentRuns,
  runAutonomyStage1,
  getAutonomyStage1Recent,
} from './api/client';
import './styles/tokens.css';
import './styles/app.css';

function App() {
  const [page, setPage] = useState('Overview');
  const [overview, setOverview] = useState<any>(null);
  const [candidates, setCandidates] = useState<any>(null);
  const [positions, setPositions] = useState<any>(null);
  const [decisions, setDecisions] = useState<any>(null);
  const [settings, setSettings] = useState<any>(null);
  const [loopsStatus, setLoopsStatus] = useState<any>(null);
  const [loopsHistory, setLoopsHistory] = useState<any>(null);
  const [reconHistory, setReconHistory] = useState<any>(null);
  const [relayHistory, setRelayHistory] = useState<any>(null);
  const [walletSummary, setWalletSummary] = useState<any>(null);
  const [modelHealth, setModelHealth] = useState<any>(null);
  const [experimentRuns, setExperimentRuns] = useState<any>(null);
  const [autonomyRecent, setAutonomyRecent] = useState<any>(null);

  const refresh = async () => {
    const [o, c, p, d, s, ls, lh, rh, relh, ws, mh, exr, ar] = await Promise.all([
      getOverview(),
      getCandidates(),
      getPositions(),
      getDecisions(),
      getSettings(),
      getLoopsStatus(),
      getLoopsHistory(20),
      getReconciliationHistory(20),
      getRelayHistory(20),
      getWalletSummary(),
      getModelHealth(),
      getExperimentRuns(20),
      getAutonomyStage1Recent(5),
    ]);
    setOverview(o);
    setCandidates(c);
    setPositions(p);
    setDecisions(d);
    setSettings(s);
    setLoopsStatus(ls);
    setLoopsHistory(lh);
    setReconHistory(rh);
    setRelayHistory(relh);
    setWalletSummary(ws);
    setModelHealth(mh);
    setExperimentRuns(exr);
    setAutonomyRecent(ar);
  };

  useEffect(() => {
    refresh();
    const t = setInterval(refresh, 20000);
    return () => clearInterval(t);
  }, []);

  return (
    <Layout page={page} setPage={setPage}>
      {page === 'Overview' && (
        <Overview
          data={overview}
          modelHealth={modelHealth}
          loopsStatus={loopsStatus}
          loopsHistory={loopsHistory}
          reconHistory={reconHistory}
          relayHistory={relayHistory}
          walletSummary={walletSummary}
          onRun={async () => {
            await runCycle();
            await refresh();
          }}
        />
      )}
      {page === 'Candidates' && <Candidates data={candidates} />}
      {page === 'Positions' && <Positions data={positions} tradesData={decisions} />}
      {page === 'Decisions' && <Decisions data={decisions} />}

      {page === 'Experiments' && (
        <Experiments
          runs={experimentRuns}
          autonomyRecent={autonomyRecent}
          onRefresh={refresh}
          onAutoRun={async (cycles: number) => {
            await runAutonomyStage1(cycles);
            await refresh();
          }}
          onRun={async (spec: any) => {
            await runExperiment(spec);
            await refresh();
          }}
        />
      )}

      {page === 'Settings' && (
        <Settings
          data={settings}
          onSave={async (s: any) => {
            await saveSettings(s);
            await refresh();
          }}
        />
      )}
    </Layout>
  );
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
