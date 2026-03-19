from app.services.execution.broker_base import BrokerBase


class HyperliquidLiveBroker(BrokerBase):
    def place_order(self, symbol: str, side: str, notional_usd: float, reduce_only: bool = False) -> dict:
        return {"accepted": False, "reason": "live_broker_not_wired", "symbol": symbol, "side": side, "notional_usd": notional_usd}

    def cancel_order(self, order_id: str) -> dict:
        return {"accepted": False, "reason": "live_broker_not_wired", "order_id": order_id}

    def get_open_orders(self) -> list[dict]:
        return []

    def get_positions(self) -> list[dict]:
        return []

    def get_fills(self) -> list[dict]:
        return []

    def flatten_position(self, symbol: str) -> dict:
        return {"accepted": False, "reason": "live_broker_not_wired", "symbol": symbol}

    def flatten_all_positions(self) -> dict:
        return {"accepted": False, "reason": "live_broker_not_wired"}


hyperliquid_live_broker = HyperliquidLiveBroker()
