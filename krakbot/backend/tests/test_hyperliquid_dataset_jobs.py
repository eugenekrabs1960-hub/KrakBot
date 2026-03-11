from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.services.hyperliquid_dataset_jobs import export_training_dataset_csv


def test_export_training_dataset_csv(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path/'jobs.db'}", future=True)
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE hyperliquid_training_features (id INTEGER PRIMARY KEY AUTOINCREMENT, ts BIGINT, environment TEXT, symbol TEXT, mid_price DOUBLE, ret_1 DOUBLE, ret_5 DOUBLE, ret_15 DOUBLE, source TEXT)"))
        conn.execute(text("INSERT INTO hyperliquid_training_features(ts, environment, symbol, mid_price, ret_1, ret_5, ret_15, source) VALUES (1000, 'testnet', 'BTC', 70000, 0.001, 0.002, 0.003, 'hyperliquid_public_v1')"))

    Session = sessionmaker(bind=engine, future=True)

    from app.services import hyperliquid_dataset_jobs as jobs
    monkeypatch.setattr(jobs, 'DATA_DIR', tmp_path / 'data' / 'training')

    with Session() as db:
        out = export_training_dataset_csv(db, symbol='BTC', limit=100)
        assert out['ok'] is True
        assert out['rows'] == 1
        assert out['path'].endswith('.csv')
