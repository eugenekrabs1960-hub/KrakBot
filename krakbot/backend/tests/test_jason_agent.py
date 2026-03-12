import time
from pathlib import Path
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.services import jason_agent


def _prep_db(path):
    eng = create_engine(f"sqlite:///{path}", future=True)
    with eng.begin() as conn:
        conn.execute(text("CREATE TABLE system_state (key TEXT PRIMARY KEY, value TEXT, updated_at TEXT)"))
        conn.execute(text("CREATE TABLE agent_decision_packets (id INTEGER PRIMARY KEY AUTOINCREMENT, ts BIGINT, agent_id TEXT, symbol TEXT, action TEXT, confidence DOUBLE, rationale TEXT, context_json TEXT, risk_json TEXT, execution_json TEXT, outcome_json TEXT, created_at TEXT)"))
        conn.execute(text("CREATE TABLE hyperliquid_training_features (id INTEGER PRIMARY KEY AUTOINCREMENT, ts BIGINT, symbol TEXT, environment TEXT, mid_price DOUBLE, ret_1 DOUBLE, ret_5 DOUBLE, ret_15 DOUBLE, source TEXT)"))
        conn.execute(text("CREATE TABLE agent_virtual_trades (id INTEGER PRIMARY KEY AUTOINCREMENT, agent_id TEXT, symbol TEXT, side TEXT, leverage DOUBLE, allocation_pct DOUBLE, margin_usd DOUBLE, entry_price DOUBLE, exit_price DOUBLE, qty DOUBLE, status TEXT, rationale TEXT, opened_at_ms BIGINT, closed_at_ms BIGINT, realized_pnl_usd DOUBLE, balance_after_usd DOUBLE, meta_json TEXT, created_at TEXT)"))
        now_ms = int(time.time() * 1000)
        for i in range(20):
            conn.execute(text("INSERT INTO hyperliquid_training_features(ts,symbol,environment,mid_price,ret_1,ret_5,ret_15,source) VALUES (:ts,'BTC','testnet',:px,0.01,0.02,0.03,'x')"), {'ts': now_ms - (20-i)*1000, 'px': 100 + i})
            conn.execute(text("INSERT INTO hyperliquid_training_features(ts,symbol,environment,mid_price,ret_1,ret_5,ret_15,source) VALUES (:ts,'ETH','testnet',:px,0.01,0.02,0.03,'x')"), {'ts': now_ms - (20-i)*1000, 'px': 200 + i})
            conn.execute(text("INSERT INTO hyperliquid_training_features(ts,symbol,environment,mid_price,ret_1,ret_5,ret_15,source) VALUES (:ts,'SOL','testnet',:px,0.01,0.02,0.03,'x')"), {'ts': now_ms - (20-i)*1000, 'px': 50 + i})
            conn.execute(text("INSERT INTO hyperliquid_training_features(ts,symbol,environment,mid_price,ret_1,ret_5,ret_15,source) VALUES (:ts,'DOGE','testnet',:px,0.015,0.01,0.005,'x')"), {'ts': now_ms - (20-i)*1000, 'px': 1 + i*0.01})
    return eng


def test_jason_run_once_opens_and_tracks(tmp_path, monkeypatch):
    eng = _prep_db(tmp_path / 'jason.db')
    Session = sessionmaker(bind=eng, future=True)

    monkeypatch.setattr(
        jason_agent,
        '_ask_openai',
        lambda snapshot, state, open_trade: jason_agent.Decision(
            action='long', symbol='BTC', leverage=5, allocation_pct=25, confidence=0.8, rationale='Momentum continuation'
        ),
    )

    with Session() as db:
        out = jason_agent.run_jason_once(db)
        assert out['ok'] is True

        st = jason_agent.get_jason_state(db)
        assert st['ok'] is True
        assert st['open_trade'] is not None

        trades = jason_agent.list_jason_trades(db, limit=10)
        assert trades['ok'] is True
        assert len(trades['items']) == 1
        assert 'unrealized_pnl_usd' in trades['items'][0]


def test_execute_jason_decision_path(tmp_path):
    eng = _prep_db(tmp_path / 'jason2.db')
    Session = sessionmaker(bind=eng, future=True)

    with Session() as db:
        out = jason_agent.execute_jason_decision(
            db,
            action='long',
            symbol='ETH',
            leverage=4,
            allocation_pct=20,
            confidence=0.7,
            rationale='ETH trend stronger than BTC on short window',
            decision_source='oauth_gpt54',
        )
        assert out['ok'] is True
        assert out['decision']['symbol'] == 'ETH'

        st = jason_agent.get_jason_state(db)
        assert st['open_trade'] is not None

        row = db.execute(text("SELECT execution_json FROM agent_decision_packets ORDER BY id DESC LIMIT 1")).mappings().first()
        assert row is not None
        assert 'oauth_gpt54' in str(row.get('execution_json'))


def test_rule_based_runner_disabled(tmp_path):
    eng = _prep_db(tmp_path / 'jason3.db')
    Session = sessionmaker(bind=eng, future=True)

    with Session() as db:
        out = jason_agent.run_jason_rule_based_once(db)
        assert out['ok'] is False
        assert out['error'] == 'fallback_disabled'


def test_set_jason_offline_marks_state(tmp_path):
    eng = _prep_db(tmp_path / 'jason4.db')
    Session = sessionmaker(bind=eng, future=True)

    with Session() as db:
        jason_agent.set_jason_offline(db, reason='oauth_unavailable')
        st = jason_agent.get_jason_state(db)
        assert st['state']['online'] is False
        assert st['state']['offline_reason'] == 'oauth_unavailable'


def test_risk_profile_set_get(tmp_path):
    eng = _prep_db(tmp_path / 'jason5.db')
    Session = sessionmaker(bind=eng, future=True)

    with Session() as db:
        out = jason_agent.get_risk_profile(db)
        assert out['profile'] == 'balanced'

        bad = jason_agent.set_risk_profile(db, 'yolo')
        assert bad['ok'] is False

        ok = jason_agent.set_risk_profile(db, 'aggressive')
        assert ok['ok'] is True

        out2 = jason_agent.get_risk_profile(db)
        assert out2['profile'] == 'aggressive'


def test_aggressive_profile_promotes_hold_when_flat(tmp_path):
    eng = _prep_db(tmp_path / 'jason6.db')
    Session = sessionmaker(bind=eng, future=True)

    with Session() as db:
        jason_agent.set_risk_profile(db, 'aggressive')
        out = jason_agent.execute_jason_decision(
            db,
            action='hold',
            symbol='BTC',
            leverage=1,
            allocation_pct=0,
            confidence=0,
            rationale='hold',
            decision_source='oauth_gpt54',
        )
        assert out['ok'] is True
        assert out['decision']['action'] in ('hold', 'long', 'short')
        if out['decision']['action'] in ('long', 'short'):
            assert float(out['decision']['allocation_pct']) >= 15.0
            assert float(out['decision']['leverage']) >= 5.0


def test_execute_jason_decision_auto_repairs_quality(tmp_path):
    eng = _prep_db(tmp_path / 'jason7.db')
    Session = sessionmaker(bind=eng, future=True)

    with Session() as db:
        out = jason_agent.execute_jason_decision(
            db,
            action='hold',
            symbol='BTC',
            leverage=1,
            allocation_pct=0,
            confidence=0.0,
            rationale='No rationale provided',
            decision_source='oauth_gpt54',
        )
        assert out['ok'] is True
        assert float(out['decision']['confidence']) > 0
        assert str(out['decision']['rationale']).strip().lower() != 'no rationale provided'


def test_open_market_symbol_allowed_and_benchmark_logged(tmp_path):
    eng = _prep_db(tmp_path / 'jason8.db')
    Session = sessionmaker(bind=eng, future=True)

    with Session() as db:
        out = jason_agent.execute_jason_decision(
            db,
            action='long',
            symbol='DOGE',
            leverage=4,
            allocation_pct=20,
            confidence=0.7,
            rationale='DOGE momentum breakout',
            decision_source='oauth_gpt54',
        )
        assert out['ok'] is True
        assert out['decision']['symbol'] == 'DOGE'

        row = db.execute(text("SELECT context_json FROM agent_decision_packets ORDER BY id DESC LIMIT 1")).mappings().first()
        assert row is not None
        ctx = str(row.get('context_json') or '')
        assert 'benchmark_reasoning' in ctx
        assert 'BTC' in ctx and 'ETH' in ctx and 'SOL' in ctx


def test_benchmark_export_job_writes_csv(tmp_path):
    eng = _prep_db(tmp_path / 'jason9.db')
    Session = sessionmaker(bind=eng, future=True)

    with Session() as db:
        jason_agent.execute_jason_decision(
            db,
            action='long',
            symbol='BTC',
            leverage=3,
            allocation_pct=10,
            confidence=0.6,
            rationale='seed row',
            decision_source='oauth_gpt54',
        )
        out = jason_agent.export_benchmark_reasoning_csv(db, limit=50)
        assert out['ok'] is True
        assert Path(out['path']).exists()
        assert Path(out['manifest_path']).exists()
