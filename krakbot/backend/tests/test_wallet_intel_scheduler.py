import asyncio

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.services.wallet_intel_scheduler import WalletIntelSchedulerService


def _prepare_sqlite_db(path):
    engine = create_engine(f"sqlite:///{path}", future=True)
    with engine.begin() as conn:
        conn.execute(text(
            """
            CREATE TABLE IF NOT EXISTS wallet_pipeline_run_ledger (
              run_id TEXT PRIMARY KEY,
              source TEXT NOT NULL,
              status TEXT NOT NULL,
              started_at_ms BIGINT NOT NULL,
              heartbeat_at_ms BIGINT NOT NULL,
              finished_at_ms BIGINT,
              duration_ms BIGINT,
              error_text TEXT,
              result_json TEXT NOT NULL DEFAULT '{}'
            )
            """
        ))
        conn.execute(text(
            """
            CREATE TABLE IF NOT EXISTS wallet_pipeline_lock (
              lock_name TEXT PRIMARY KEY,
              owner_run_id TEXT,
              acquired_at_ms BIGINT,
              heartbeat_at_ms BIGINT,
              updated_at TEXT
            )
            """
        ))
    return engine


def test_scheduler_single_run_lock(monkeypatch, tmp_path):
    engine = _prepare_sqlite_db(tmp_path / 'wsched.db')
    Session = sessionmaker(bind=engine, future=True)

    service = WalletIntelSchedulerService()

    # Swap SessionLocal used inside service module to our sqlite session factory.
    monkeypatch.setattr('app.services.wallet_intel_scheduler.SessionLocal', Session)

    async def fake_fetch(self):
        await asyncio.sleep(0)
        return []

    monkeypatch.setattr(WalletIntelSchedulerService, '_fetch_provider_events', fake_fetch)

    def fake_pipeline_run(self, db, provider_events=None):
        return {'ok': True, 'run_id': 'fake', 'signal': {'signal': 'neutral'}}

    monkeypatch.setattr('app.services.wallet_intel_scheduler.WalletIntelService.run_pipeline', fake_pipeline_run)

    out1 = asyncio.run(service.run_once(source='test'))
    assert out1['ok'] is True
    assert out1['status'] == 'success'

    with Session() as db:
        row = db.execute(text("SELECT status FROM wallet_pipeline_run_ledger ORDER BY started_at_ms DESC LIMIT 1")).first()
        lock = db.execute(text("SELECT owner_run_id FROM wallet_pipeline_lock WHERE lock_name='wallet_pipeline' LIMIT 1")).first()
    assert row is not None and row[0] == 'success'
    assert lock is not None and lock[0] is None

    # Simulate held lock and verify scheduler skips overlap.
    with Session.begin() as db:
        db.execute(
            text(
                """
                INSERT INTO wallet_pipeline_lock(lock_name, owner_run_id, acquired_at_ms, heartbeat_at_ms)
                VALUES ('wallet_pipeline', 'other_run', 9999999999999, 9999999999999)
                ON CONFLICT(lock_name) DO UPDATE SET owner_run_id='other_run', acquired_at_ms=9999999999999, heartbeat_at_ms=9999999999999
                """
            )
        )

    out2 = asyncio.run(service.run_once(source='test'))
    assert out2['ok'] is False
    assert out2['reason'] == 'lock_held'
