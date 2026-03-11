from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.services.hyperliquid_state_store import (
    compute_latest_hyperliquid_risk_snapshot,
    list_latest_hyperliquid_account_snapshots,
    list_latest_hyperliquid_position_snapshots,
    persist_hyperliquid_snapshots,
)


def _prep_db(path):
    eng = create_engine(f"sqlite:///{path}", future=True)
    with eng.begin() as conn:
        conn.execute(text("CREATE TABLE hyperliquid_account_snapshots (id INTEGER PRIMARY KEY AUTOINCREMENT, ts BIGINT, environment TEXT, equity_usd DOUBLE, available_margin_usd DOUBLE, maintenance_margin_usd DOUBLE, payload_json TEXT)"))
        conn.execute(text("CREATE TABLE hyperliquid_position_snapshots (id INTEGER PRIMARY KEY AUTOINCREMENT, ts BIGINT, environment TEXT, market TEXT, qty DOUBLE, avg_entry_price DOUBLE, realized_pnl_usd DOUBLE, unrealized_pnl_usd DOUBLE, leverage DOUBLE, liquidation_price DOUBLE, payload_json TEXT)"))
    return eng


def test_state_store_persist_and_list(tmp_path):
    eng = _prep_db(tmp_path / 'hl_state.db')
    Session = sessionmaker(bind=eng, future=True)

    with Session() as db:
        out = persist_hyperliquid_snapshots(
            db,
            environment='testnet',
            account={'equity_usd': 1000, 'available_margin_usd': 800, 'maintenance_margin_usd': 100},
            positions=[{'market': 'SOL-PERP', 'qty': 1, 'avg_entry_price': 100, 'realized_pnl_usd': 0, 'unrealized_pnl_usd': 3, 'leverage': 3}],
        )
        assert out['account_written'] == 1
        assert out['position_written'] == 1

    with Session() as db:
        acc = list_latest_hyperliquid_account_snapshots(db, limit=5)
        pos = list_latest_hyperliquid_position_snapshots(db, limit=5)
        assert len(acc) == 1
        assert len(pos) == 1
        assert acc[0]['environment'] == 'testnet'
        assert pos[0]['market'] == 'SOL-PERP'

        risk = compute_latest_hyperliquid_risk_snapshot(db)
        assert risk['ok'] is True
        assert risk['positions_count'] == 1
        assert risk['total_notional_usd'] == 100.0
        assert risk['position_concentration_pct'] == 100.0
