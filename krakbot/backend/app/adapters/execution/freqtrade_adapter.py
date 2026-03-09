from app.adapters.execution.base import ExecutionEngine, OrderIntent


class FreqtradeExecutionAdapter(ExecutionEngine):
    """
    Adapter boundary: keep Freqtrade details inside this module.
    TODO: implement real integration via freqtrade RPC/client process bridge.
    """

    def submit_order(self, intent: OrderIntent) -> dict:
        return {"accepted": True, "engine": "freqtrade", "intent": intent.__dict__}

    def cancel_order(self, order_id: str) -> dict:
        return {"cancelled": False, "order_id": order_id}

    def fetch_open_orders(self) -> list[dict]:
        return []

    def fetch_fills(self, since_ts: str | None = None) -> list[dict]:
        return []

    def health(self) -> dict:
        return {"engine": "freqtrade", "ok": True}
