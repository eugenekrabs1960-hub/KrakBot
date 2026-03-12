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
        for i in range(20):
            conn.execute(text("INSERT INTO hyperliquid_training_features(ts,symbol,environment,mid_price,ret_1,ret_5,ret_15,source) VALUES (:ts,'BTC','testnet',:px,0.01,0.02,0.03,'x')"), {'ts': 1000 + i, 'px': 100 + i})
            conn.execute(text("INSERT INTO hyperliquid_training_features(ts,symbol,environment,mid_price,ret_1,ret_5,ret_15,source) VALUES (:ts,'ETH','testnet',:px,0.01,0.02,0.03,'x')"), {'ts': 1000 + i, 'px': 200 + i})
            conn.execute(text("INSERT INTO hyperliquid_training_features(ts,symbol,environment,mid_price,ret_1,ret_5,ret_15,source) VALUES (:ts,'SOL','testnet',:px,0.01,0.02,0.03,'x')"), {'ts': 1000 + i, 'px': 50 + i})
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
