import json
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.services import model_connectors


def _prep_db(path):
    eng = create_engine(f"sqlite:///{path}", future=True)
    with eng.begin() as conn:
        conn.execute(text("CREATE TABLE IF NOT EXISTS system_state (key TEXT PRIMARY KEY, value TEXT, updated_at TEXT)"))
    return eng


def test_registry_default_and_roundtrip(tmp_path):
    eng = _prep_db(tmp_path / 'mc1.db')
    Session = sessionmaker(bind=eng, future=True)
    with Session() as db:
        reg = model_connectors.get_model_registry(db)
        assert reg['ok'] is True
        assert any(m.get('id') == 'qwen3.5-9b-local' for m in reg.get('models', []))

        custom = {'version': 1, 'models': [{'id': 'x', 'provider_type': 'openai_compatible', 'base_url': 'http://127.0.0.1:9/v1'}]}
        out = model_connectors.set_model_registry(db, custom)
        assert out['ok'] is True

        reg2 = model_connectors.get_model_registry(db)
        assert reg2['models'][0]['id'] == 'x'


def test_readiness_model_not_found(tmp_path):
    eng = _prep_db(tmp_path / 'mc2.db')
    Session = sessionmaker(bind=eng, future=True)
    with Session() as db:
        out = model_connectors.check_model_readiness(db, 'missing')
        assert out['ok'] is False
        assert out['error'] == 'model_not_found'
