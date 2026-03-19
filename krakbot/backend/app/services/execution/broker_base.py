from abc import ABC, abstractmethod


class BrokerBase(ABC):
    @abstractmethod
    def place_order(self, symbol: str, side: str, notional_usd: float, reduce_only: bool = False) -> dict: ...

    @abstractmethod
    def cancel_order(self, order_id: str) -> dict: ...

    @abstractmethod
    def get_open_orders(self) -> list[dict]: ...

    @abstractmethod
    def get_positions(self) -> list[dict]: ...

    @abstractmethod
    def get_fills(self) -> list[dict]: ...

    @abstractmethod
    def flatten_position(self, symbol: str) -> dict: ...

    @abstractmethod
    def flatten_all_positions(self) -> dict: ...
