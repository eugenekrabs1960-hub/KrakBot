from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.services.model_lab import (
    get_active_execution_model,
    get_active_model_for_paper,
    list_job_history,
    set_active_execution_model,
    set_active_model_for_paper,
    strategy_benchmarks,
    train_baseline,
)


def _prep_db(path):
    eng = create_engine(f"sqlite:///{path}", future=True)
    with eng.begin() as conn:
        conn.execute(text("CREATE TABLE hyperliquid_training_features (id INTEGER PRIMARY KEY AUTOINCREMENT, ts BIGINT, symbol TEXT, environment TEXT, mid_price DOUBLE, ret_1 DOUBLE, ret_5 DOUBLE, ret_15 DOUBLE, source TEXT)"))
        conn.execute(text("CREATE TABLE system_state (key TEXT PRIMARY KEY, value TEXT, updated_at TEXT)"))
        px = 100.0
        for i in range(120):
            px += 0.1
            conn.execute(
                text("INSERT INTO hyperliquid_training_features(ts, symbol, environment, mid_price, ret_1, ret_5, ret_15, source) VALUES (:ts, 'BTC', 'testnet', :px, :r1, :r5, :r15, 'x')"),
                {'ts': 1000 + i, 'px': px, 'r1': 0.001 if i % 2 == 0 else -0.001, 'r5': 0.002 if i % 3 == 0 else -0.002, 'r15': 0.003 if i % 4 == 0 else -0.003},
            )
    return eng


def test_train_baseline_and_bench(tmp_path, monkeypatch):
    eng = _prep_db(tmp_path / 'ml.db')
    Session = sessionmaker(bind=eng, future=True)

    from app.services import model_lab
    monkeypatch.setattr(model_lab, 'MODEL_DIR', tmp_path / 'data' / 'models')
    monkeypatch.setattr(model_lab, 'JOB_LOG_PATH', (tmp_path / 'data' / 'models' / 'model_lab_jobs.jsonl'))

    with Session() as db:
        out = train_baseline(db, symbol='BTC', limit=1000)
        assert out['ok'] is True
        assert out['test_rows'] > 0

        bench = strategy_benchmarks(db, symbol='BTC', limit=1000)
        assert bench['ok'] is True
        assert len(bench['items']) == 3

        hist = list_job_history(10)
        assert hist['ok'] is True
        assert len(hist['items']) >= 1


def test_promote_toggle_requires_confirmation(tmp_path, monkeypatch):
    eng = _prep_db(tmp_path / 'ml2.db')
    Session = sessionmaker(bind=eng, future=True)

    with Session() as db:
        out = set_active_model_for_paper(db, symbol='BTC', model_path='/tmp/model.json', confirm_phrase='NOPE')
        assert out['ok'] is False

        ok = set_active_model_for_paper(db, symbol='BTC', model_path='/tmp/model.json', confirm_phrase='PROMOTE')
        assert ok['ok'] is True

        active = get_active_model_for_paper(db)
        assert active['ok'] is True
        assert active['item']['model_path'] == '/tmp/model.json'


def test_execution_model_switch_requires_confirmation(tmp_path):
    eng = _prep_db(tmp_path / 'ml3.db')
    Session = sessionmaker(bind=eng, future=True)

    with Session() as db:
        out = set_active_execution_model(db, agent_id='agent_alpha', confirm_phrase='NOPE')
        assert out['ok'] is False

        ok = set_active_execution_model(db, agent_id='agent_alpha', confirm_phrase='SWITCH')
        assert ok['ok'] is True

        active = get_active_execution_model(db)
        assert active['ok'] is True
        assert active['item']['agent_id'] == 'agent_alpha'


def test_execution_model_switch_rejects_empty_and_handles_duplicate(tmp_path):
    eng = _prep_db(tmp_path / 'ml4.db')
    Session = sessionmaker(bind=eng, future=True)

    with Session() as db:
        bad = set_active_execution_model(db, agent_id='   ', confirm_phrase='SWITCH')
        assert bad['ok'] is False
        assert bad['error'] == 'invalid_agent_id'

        first = set_active_execution_model(db, agent_id='agent_beta', confirm_phrase='SWITCH')
        assert first['ok'] is True
        assert first.get('unchanged') is not True

        second = set_active_execution_model(db, agent_id='agent_beta', confirm_phrase='SWITCH')
        assert second['ok'] is True
        assert second.get('unchanged') is True
        assert second['item']['agent_id'] == 'agent_beta'
