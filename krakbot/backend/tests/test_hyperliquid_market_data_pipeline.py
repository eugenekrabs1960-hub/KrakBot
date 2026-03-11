from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.services.hyperliquid_market_data import HyperliquidMarketDataService, list_latest_training_features


class _Resp:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def _prep_db(path):
    eng = create_engine(f"sqlite:///{path}", future=True)
    with eng.begin() as conn:
        conn.execute(text("CREATE TABLE hyperliquid_market_mids (id INTEGER PRIMARY KEY AUTOINCREMENT, ts BIGINT, environment TEXT, symbol TEXT, mid_price DOUBLE)"))
        conn.execute(text("CREATE TABLE hyperliquid_market_meta_snapshots (id INTEGER PRIMARY KEY AUTOINCREMENT, ts BIGINT, environment TEXT, symbols_count INT, payload_json TEXT)"))
        conn.execute(text("CREATE TABLE hyperliquid_training_features (id INTEGER PRIMARY KEY AUTOINCREMENT, ts BIGINT, environment TEXT, symbol TEXT, mid_price DOUBLE, ret_1 DOUBLE, ret_5 DOUBLE, ret_15 DOUBLE, source TEXT)"))
    return eng


def test_collect_once_writes_mids_and_features(tmp_path):
    eng = _prep_db(tmp_path / 'hl_market.db')
    Session = sessionmaker(bind=eng, future=True)

    calls = {'n': 0}

    def fake_post(url, json, timeout=20):
        calls['n'] += 1
        if json.get('type') == 'allMids':
            return _Resp({'BTC': '70000', 'ETH': '3500', 'SOL': '180'})
        if json.get('type') == 'meta':
            return _Resp({'universe': [{'name': 'BTC'}, {'name': 'ETH'}, {'name': 'SOL'}]})
        return _Resp({})

    svc = HyperliquidMarketDataService(environment='testnet', post=fake_post)

    with Session() as db:
        out = svc.collect_once(db, symbols_limit=3)
        assert out.ok is True
        assert out.mids_written == 3
        assert out.symbols_count == 3

    with Session() as db:
        feats = list_latest_training_features(db, limit=10)
        assert len(feats) == 3
        assert {f['symbol'] for f in feats} == {'BTC', 'ETH', 'SOL'}
