from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.services.hyperliquid_dataset_jobs import build_labeled_dataset_v1, export_training_dataset_csv


def _prep_db(path):
    engine = create_engine(f"sqlite:///{path}", future=True)
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE hyperliquid_training_features (id INTEGER PRIMARY KEY AUTOINCREMENT, ts BIGINT, environment TEXT, symbol TEXT, mid_price DOUBLE, ret_1 DOUBLE, ret_5 DOUBLE, ret_15 DOUBLE, source TEXT)"))
        for i in range(80):
            px = 70000 + i * 10
            conn.execute(
                text("INSERT INTO hyperliquid_training_features(ts, environment, symbol, mid_price, ret_1, ret_5, ret_15, source) VALUES (:ts, 'testnet', 'BTC', :px, 0.0, 0.0, 0.0, 'hyperliquid_public_v1')"),
                {'ts': 1000 + i, 'px': px},
            )
    return engine


def test_export_training_dataset_csv(tmp_path, monkeypatch):
    engine = _prep_db(tmp_path / 'jobs.db')
    Session = sessionmaker(bind=engine, future=True)

    from app.services import hyperliquid_dataset_jobs as jobs
    monkeypatch.setattr(jobs, 'DATA_DIR', tmp_path / 'data' / 'training')

    with Session() as db:
        out = export_training_dataset_csv(db, symbol='BTC', limit=100)
        assert out['ok'] is True
        assert out['rows'] > 0
        assert out['path'].endswith('.csv')
        assert out['manifest_path'].endswith('.manifest.json')
        assert Path(out['path']).exists()
        assert Path(out['manifest_path']).exists()


def test_build_labeled_dataset_v1(tmp_path, monkeypatch):
    engine = _prep_db(tmp_path / 'jobs2.db')
    Session = sessionmaker(bind=engine, future=True)

    from app.services import hyperliquid_dataset_jobs as jobs
    monkeypatch.setattr(jobs, 'DATA_DIR', tmp_path / 'data' / 'training')

    with Session() as db:
        out = build_labeled_dataset_v1(db, symbol='BTC', limit=80)
        assert out['ok'] is True
        assert out['rows'] == 80
        txt = Path(out['path']).read_text(encoding='utf-8')
        assert 'y_ret_fwd_5' in txt.splitlines()[0]
