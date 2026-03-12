from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.services.live_trading_guard import (
    disable_live_trading_guard,
    enable_live_trading_guard,
    enforce_live_trading_order_guard,
    get_live_trading_guard,
)


def test_live_trading_guard_enable_disable_and_caps(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path/'liveguard.db'}", future=True)
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE system_state (key TEXT PRIMARY KEY, value JSON, updated_at TEXT)"))

    Session = sessionmaker(bind=engine, future=True)
    with Session() as db:
        s0 = get_live_trading_guard(db)
        assert s0['ok'] is True
        assert s0['item']['enabled'] is False

        bad = enable_live_trading_guard(
            db,
            confirm_phrase='NOPE',
            max_notional_usd_per_order=500,
            max_daily_loss_usd=200,
            allowed_agents=['jason'],
        )
        assert bad['ok'] is False

        ok = enable_live_trading_guard(
            db,
            confirm_phrase='LIVE_ON',
            max_notional_usd_per_order=500,
            max_daily_loss_usd=200,
            allowed_agents=['jason'],
        )
        assert ok['ok'] is True
        assert ok['item']['enabled'] is True

        blocked = enforce_live_trading_order_guard(db, strategy_instance_id='other_agent', notional_usd=100)
        assert blocked['ok'] is False

        capped = enforce_live_trading_order_guard(db, strategy_instance_id='jason', notional_usd=700)
        assert capped['ok'] is False

        allowed = enforce_live_trading_order_guard(db, strategy_instance_id='jason', notional_usd=100)
        assert allowed['ok'] is True

        off = disable_live_trading_guard(db, confirm_phrase='LIVE_OFF')
        assert off['ok'] is True
        assert off['item']['enabled'] is False
