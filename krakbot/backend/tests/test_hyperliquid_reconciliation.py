from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.services.hyperliquid_reconciliation import HyperliquidReconciliationService


class _FakeAccount:
    def __init__(self, equity_usd):
        self.equity_usd = equity_usd
        self.available_margin_usd = 1000
        self.maintenance_margin_usd = 100
        self.venue = 'hyperliquid'
        self.venue_payload = {}


class _FakePosition:
    def __init__(self, market, qty):
        self.strategy_instance_id = 'venue_account'
        self.venue = 'hyperliquid'
        self.market = market
        self.qty = qty
        self.avg_entry_price = 100
        self.realized_pnl_usd = 0
        self.unrealized_pnl_usd = 0
        self.leverage = 2
        self.liquidation_price = None
        self.venue_payload = {}


class _FakeAdapter:
    def __init__(self):
        self.flip = False

    def fetch_account_state(self):
        return _FakeAccount(1200 if self.flip else 1000)

    def fetch_positions(self):
        q = 2 if self.flip else 1
        return [_FakePosition('SOL-PERP', q)]


def _prep_db(path):
    eng = create_engine(f"sqlite:///{path}", future=True)
    with eng.begin() as conn:
        conn.execute(text("CREATE TABLE reconciliations (id INTEGER PRIMARY KEY AUTOINCREMENT, strategy_instance_id TEXT, kind TEXT, status TEXT, details TEXT, ts BIGINT)"))
        conn.execute(text("CREATE TABLE worker_checkpoints (worker_name TEXT PRIMARY KEY, checkpoint TEXT NOT NULL, updated_at TEXT)"))
    return eng


def test_hyperliquid_reconciliation_detects_change(tmp_path):
    eng = _prep_db(tmp_path / 'recon.db')
    Session = sessionmaker(bind=eng, future=True)
    adapter = _FakeAdapter()
    svc = HyperliquidReconciliationService(adapter=adapter)

    with Session() as db:
        first = svc.run_once(db)
        assert first['status'] == 'ok'

    adapter.flip = True
    with Session() as db:
        second = svc.run_once(db)
        assert second['status'] == 'drift_detected'
        rows = db.execute(text("SELECT COUNT(*) FROM reconciliations WHERE kind='hyperliquid_state'"))
        assert rows.scalar_one() == 2
