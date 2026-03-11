from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.services.execution_preferences import get_default_execution_venue, set_default_execution_venue


def test_execution_venue_preference_roundtrip(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path/'prefs.db'}", future=True)
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE system_state (key TEXT PRIMARY KEY, value JSON, updated_at TEXT)"))

    Session = sessionmaker(bind=engine, future=True)
    with Session() as db:
        assert get_default_execution_venue(db) == 'paper'
        out = set_default_execution_venue(db, 'hyperliquid')
        assert out == 'hyperliquid'
        assert get_default_execution_venue(db) == 'hyperliquid'
        out2 = set_default_execution_venue(db, 'invalid')
        assert out2 == 'paper'
        assert get_default_execution_venue(db) == 'paper'
