from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.services.hyperliquid_market_scheduler import HyperliquidMarketScheduler


def test_scheduler_run_once_writes_checkpoint(monkeypatch, tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path/'sched.db'}", future=True)
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE worker_checkpoints (worker_name TEXT PRIMARY KEY, checkpoint TEXT NOT NULL, updated_at TEXT)"))

    Session = sessionmaker(bind=engine, future=True)
    monkeypatch.setattr('app.services.hyperliquid_market_scheduler.SessionLocal', Session)

    class _FakeSvc:
        def __init__(self, environment=None):
            self.environment = environment

        def collect_once(self, db, symbols_limit=0):
            return type('R', (), {'__dict__': {'ok': True, 'ts': 1, 'mids_written': 2, 'features_written': 2, 'symbols_count': 2}})()

    monkeypatch.setattr('app.services.hyperliquid_market_scheduler.HyperliquidMarketDataService', _FakeSvc)

    sched = HyperliquidMarketScheduler()
    out = sched.run_once()
    assert out['ok'] is True

    with Session() as db:
        row = db.execute(text("SELECT checkpoint FROM worker_checkpoints WHERE worker_name='hyperliquid_market_collector' LIMIT 1")).first()
        assert row is not None
