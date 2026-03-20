from datetime import datetime, timezone
import uuid

from app.services.execution.broker_base import BrokerBase
from app.services.ingest.hyperliquid_market import fetch_market_snapshot


class PaperBroker(BrokerBase):
    def __init__(self):
        self.positions: dict[str, float] = {}
        self.fills: list[dict] = []

    def _paper_mark(self, symbol: str) -> float:
        coin = symbol.replace('-PERP', '')
        try:
            m = fetch_market_snapshot(coin)
            px = float(m.get('mark_price') or m.get('last_price') or 0.0)
            if px > 0:
                return px
        except Exception:
            pass
        return 100.0

    def place_order(self, symbol: str, side: str, notional_usd: float, reduce_only: bool = False) -> dict:
        px = self._paper_mark(symbol)
        qty = notional_usd / px if px > 0 else 0.0
        if side == "sell":
            qty = -qty
        self.positions[symbol] = self.positions.get(symbol, 0.0) + qty
        fill = {
            "order_id": f"paper_{uuid.uuid4().hex[:10]}",
            "symbol": symbol,
            "side": side,
            "notional_usd": notional_usd,
            "fill_price": px,
            "filled_qty": qty,
            "ts": datetime.now(timezone.utc).isoformat(),
        }
        self.fills.append(fill)
        return {"accepted": True, **fill}

    def cancel_order(self, order_id: str) -> dict:
        return {"accepted": True, "order_id": order_id}

    def get_open_orders(self) -> list[dict]:
        return []

    def get_positions(self) -> list[dict]:
        return [{"symbol": k, "qty": v} for k, v in self.positions.items() if abs(v) > 1e-9]

    def get_fills(self) -> list[dict]:
        return self.fills[-100:]

    def flatten_position(self, symbol: str) -> dict:
        self.positions[symbol] = 0.0
        return {"accepted": True, "symbol": symbol}

    def flatten_all_positions(self) -> dict:
        for k in list(self.positions):
            self.positions[k] = 0.0
        return {"accepted": True}


paper_broker = PaperBroker()
