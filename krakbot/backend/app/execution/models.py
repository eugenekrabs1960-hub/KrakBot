from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

OrderType = Literal['market', 'limit']
OrderSide = Literal['buy', 'sell']
OrderStatus = Literal['submitted', 'accepted', 'partially_filled', 'filled', 'canceled', 'rejected']


@dataclass(slots=True)
class VenueContext:
    venue: str
    environment: Literal['testnet', 'mainnet'] = 'testnet'
    account_ref: str | None = None
    adapter_version: str = 'v1'


@dataclass(slots=True)
class OrderIntent:
    strategy_instance_id: str
    market: str
    side: OrderSide
    qty: float
    order_type: OrderType = 'market'
    limit_price: float | None = None
    reduce_only: bool = False
    client_order_id: str | None = None
    idempotency_key: str | None = None
    venue_context: VenueContext = field(default_factory=lambda: VenueContext(venue='paper'))
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class OrderState:
    order_id: str
    strategy_instance_id: str
    venue: str
    market: str
    side: OrderSide
    qty: float
    status: OrderStatus
    filled_qty: float = 0.0
    avg_fill_price: float | None = None
    reject_reason: str | None = None
    venue_payload: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class FillEvent:
    execution_id: str
    order_id: str
    strategy_instance_id: str
    venue: str
    market: str
    side: OrderSide
    qty: float
    price: float
    fee_usd: float = 0.0
    venue_payload: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class PositionState:
    strategy_instance_id: str
    venue: str
    market: str
    qty: float
    avg_entry_price: float
    realized_pnl_usd: float
    unrealized_pnl_usd: float = 0.0
    leverage: float | None = None
    liquidation_price: float | None = None
    venue_payload: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class AccountState:
    venue: str
    equity_usd: float
    available_margin_usd: float | None = None
    maintenance_margin_usd: float | None = None
    venue_payload: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class RiskDecision:
    allowed: bool
    reason_code: str = 'ok'
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ExecutionReport:
    accepted: bool
    order_state: OrderState | None = None
    fill_event: FillEvent | None = None
    error_code: str | None = None
    message: str | None = None
    venue_payload: dict[str, Any] = field(default_factory=dict)
