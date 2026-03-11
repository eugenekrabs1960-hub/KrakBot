from __future__ import annotations

from typing import Protocol

from .models import AccountState, ExecutionReport, OrderIntent, PositionState, RiskDecision


class VenueAdapter(Protocol):
    name: str

    def submit_order(self, intent: OrderIntent) -> ExecutionReport:
        ...

    def cancel_order(self, order_id: str) -> dict:
        ...

    def fetch_account_state(self) -> AccountState | None:
        ...

    def fetch_positions(self) -> list[PositionState]:
        ...

    def health(self) -> dict:
        ...


class RiskEvaluator(Protocol):
    def evaluate(self, intent: OrderIntent) -> RiskDecision:
        ...
