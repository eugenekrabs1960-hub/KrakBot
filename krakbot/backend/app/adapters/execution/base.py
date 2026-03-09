from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Literal


@dataclass
class OrderIntent:
    strategy_instance_id: str
    market: str
    side: Literal["buy", "sell"]
    qty: float
    order_type: Literal["market", "limit"] = "market"
    limit_price: float | None = None


class ExecutionEngine(ABC):
    @abstractmethod
    def submit_order(self, intent: OrderIntent) -> dict: ...

    @abstractmethod
    def cancel_order(self, order_id: str) -> dict: ...

    @abstractmethod
    def fetch_open_orders(self) -> list[dict]: ...

    @abstractmethod
    def fetch_fills(self, since_ts: str | None = None) -> list[dict]: ...

    @abstractmethod
    def health(self) -> dict: ...
