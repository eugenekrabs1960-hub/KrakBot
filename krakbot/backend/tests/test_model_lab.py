from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.services.model_lab import strategy_benchmarks, train_baseline


def _prep_db(path):
    eng = create_engine(f"sqlite:///{path}", future=True)
    with eng.begin() as conn:
        conn.execute(text("CREATE TABLE hyperliquid_training_features (id INTEGER PRIMARY KEY AUTOINCREMENT, ts BIGINT, symbol TEXT, environment TEXT, mid_price DOUBLE, ret_1 DOUBLE, ret_5 DOUBLE, ret_15 DOUBLE, source TEXT)"))
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

    with Session() as db:
        out = train_baseline(db, symbol='BTC', limit=1000)
        assert out['ok'] is True
        assert out['test_rows'] > 0

        bench = strategy_benchmarks(db, symbol='BTC', limit=1000)
        assert bench['ok'] is True
        assert len(bench['items']) == 3
