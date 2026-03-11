from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.services.hyperliquid_market_data import HyperliquidMarketDataService


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
        conn.execute(text("CREATE TABLE hyperliquid_training_features (id INTEGER PRIMARY KEY AUTOINCREMENT, ts BIGINT, environment TEXT, symbol TEXT, mid_price DOUBLE, ret_1 DOUBLE, ret_5 DOUBLE, ret_15 DOUBLE, source TEXT)"))
    return eng


def test_backfill_candles_writes_rows(tmp_path):
    eng = _prep_db(tmp_path / 'bf.db')
    Session = sessionmaker(bind=eng, future=True)

    def fake_post(url, json, timeout=20):
        if json.get('type') == 'candleSnapshot':
            return _Resp([
                {'t': 1000, 'c': '100.0'},
                {'t': 2000, 'c': '101.0'},
                {'t': 3000, 'c': '102.0'},
            ])
        return _Resp({})

    svc = HyperliquidMarketDataService(environment='testnet', post=fake_post)
    with Session() as db:
        out = svc.backfill_candles(db, symbol='BTC', interval='1m', start_time_ms=1000, end_time_ms=3000)
        assert out.ok is True
        assert out.mids_written == 3
        assert out.features_written >= 1

        mids = db.execute(text("SELECT COUNT(*) FROM hyperliquid_market_mids WHERE symbol='BTC'"))
        feats = db.execute(text("SELECT COUNT(*) FROM hyperliquid_training_features WHERE symbol='BTC'"))
        assert mids.scalar_one() == 3
        assert feats.scalar_one() >= 1
