from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.services import qwen_challenger


def _prep_db(path):
    eng = create_engine(f"sqlite:///{path}", future=True)
    with eng.begin() as conn:
        conn.execute(text("CREATE TABLE IF NOT EXISTS system_state (key TEXT PRIMARY KEY, value TEXT, updated_at TEXT)"))
        conn.execute(text("CREATE TABLE IF NOT EXISTS hyperliquid_training_features (id INTEGER PRIMARY KEY AUTOINCREMENT, ts BIGINT, symbol TEXT, environment TEXT, mid_price DOUBLE, ret_1 DOUBLE, ret_5 DOUBLE, ret_15 DOUBLE, source TEXT)"))
        conn.execute(text("CREATE TABLE IF NOT EXISTS agent_virtual_trades (id INTEGER PRIMARY KEY AUTOINCREMENT, agent_id TEXT, symbol TEXT, side TEXT, leverage DOUBLE, allocation_pct DOUBLE, margin_usd DOUBLE, entry_price DOUBLE, qty DOUBLE, status TEXT, rationale TEXT, opened_at_ms BIGINT, exit_price DOUBLE, closed_at_ms BIGINT, realized_pnl_usd DOUBLE, balance_after_usd DOUBLE, meta_json TEXT)"))
        conn.execute(text("CREATE TABLE IF NOT EXISTS agent_decision_packets (id INTEGER PRIMARY KEY AUTOINCREMENT, ts BIGINT, agent_id TEXT, symbol TEXT, action TEXT, confidence DOUBLE, rationale TEXT, context_json TEXT, risk_json TEXT, execution_json TEXT, outcome_json TEXT)"))
        conn.execute(text("INSERT INTO hyperliquid_training_features(ts,symbol,environment,mid_price,ret_1,ret_5,ret_15,source) VALUES (9999999999999,'BTC','testnet',70000,0.01,0.02,0.03,'x')"))
        conn.execute(text("INSERT INTO system_state(key,value,updated_at) VALUES ('agent_jason_state', :v, 'now')"), {'v': '{"balance_usd":1000,"active":true,"online":true}'})
    return eng


def test_qwen_run_once_with_mocked_provider(tmp_path, monkeypatch):
    eng = _prep_db(tmp_path / 'qwen1.db')
    Session = sessionmaker(bind=eng, future=True)

    def fake_query(base, model, payload, headers=None):
        return ('{"action":"long","symbol":"BTC","leverage":4,"allocation_pct":10,"confidence":0.71,"rationale":"local edge"}', 11.0, {})

    monkeypatch.setattr(qwen_challenger, '_query_local_openai_compatible', fake_query)

    with Session() as db:
        # ensure registry available from default loader via empty system_state fallback
        out = qwen_challenger.run_qwen_once(db)
        assert out['ok'] is True
        assert out['agent_id'] == 'qwen_local_challenger'
        assert out['decision']['symbol'] == 'BTC'
