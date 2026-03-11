from __future__ import annotations

import time
from typing import Any, Callable

import requests

from app.core.config import settings
from app.execution.models import AccountState, ExecutionReport, OrderIntent, OrderState, PositionState


class HyperliquidExecutionAdapter:
    """Phase-B native adapter for Hyperliquid execution/account primitives.

    This intentionally keeps signing/auth pluggable so we can harden auth flows later
    without changing the adapter contract.
    """

    name = 'hyperliquid'

    def __init__(
        self,
        environment: str | None = None,
        base_url: str | None = None,
        account_address: str | None = None,
        signer: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
        post: Callable[..., Any] | None = None,
    ):
        self.environment = environment or settings.hyperliquid_environment
        self.base_url = (base_url or settings.hyperliquid_base_url).rstrip('/')
        self.account_address = account_address or settings.hyperliquid_account_address
        self.signer = signer
        self._post = post or requests.post

    def _post_json(self, path: str, payload: dict[str, Any]) -> Any:
        resp = self._post(f'{self.base_url}{path}', json=payload, timeout=20)
        resp.raise_for_status()
        return resp.json()

    def submit_order(self, intent: OrderIntent) -> ExecutionReport:
        if not settings.hyperliquid_enabled:
            return ExecutionReport(accepted=False, error_code='venue_disabled', message='hyperliquid disabled')

        if self.signer is None:
            return ExecutionReport(
                accepted=False,
                error_code='auth_not_configured',
                message='hyperliquid signer not configured',
            )

        coin = intent.market.replace('-PERP', '').replace('/USD', '')
        order_wire = {
            'a': coin,
            'b': intent.side == 'buy',
            'p': str(intent.limit_price or 0),
            's': str(intent.qty),
            'r': bool(intent.reduce_only),
            't': {'limit': {'tif': 'Gtc'}} if intent.order_type == 'limit' else {'trigger': {'isMarket': True}},
            'c': intent.client_order_id or intent.idempotency_key or f"kb_{int(time.time() * 1000)}",
        }
        action = {'type': 'order', 'orders': [order_wire], 'grouping': 'na'}
        signature = self.signer(action)
        payload = {
            'action': action,
            'nonce': int(time.time() * 1000),
            'signature': signature,
        }

        data = self._post_json('/exchange', payload)
        statuses = ((data or {}).get('response') or {}).get('data') or {}
        status = statuses.get('statuses', [{}])[0] if isinstance(statuses, dict) else {}

        if 'error' in status:
            return ExecutionReport(
                accepted=False,
                error_code='venue_rejected',
                message=str(status.get('error')),
                venue_payload={'raw': data},
            )

        oid = (((status.get('resting') or {}).get('oid')) or ((status.get('filled') or {}).get('oid')) or 'unknown')
        avg_px = (status.get('filled') or {}).get('avgPx')
        order_state = OrderState(
            order_id=str(oid),
            strategy_instance_id=intent.strategy_instance_id,
            venue=self.name,
            market=intent.market,
            side=intent.side,
            qty=float(intent.qty),
            status='accepted',
            filled_qty=float(intent.qty if avg_px else 0.0),
            avg_fill_price=float(avg_px) if avg_px is not None else None,
            venue_payload={'raw': status},
        )
        return ExecutionReport(accepted=True, order_state=order_state, venue_payload={'raw': data})

    def cancel_order(self, order_id: str) -> dict:
        if not settings.hyperliquid_enabled:
            return {'ok': False, 'error_code': 'venue_disabled', 'order_id': order_id, 'venue': self.name}
        if self.signer is None:
            return {'ok': False, 'error_code': 'auth_not_configured', 'order_id': order_id, 'venue': self.name}

        action = {'type': 'cancel', 'cancels': [{'oid': int(order_id) if str(order_id).isdigit() else order_id}]}
        payload = {'action': action, 'nonce': int(time.time() * 1000), 'signature': self.signer(action)}
        data = self._post_json('/exchange', payload)
        return {'ok': True, 'order_id': order_id, 'venue': self.name, 'raw': data}

    def fetch_account_state(self) -> AccountState | None:
        if not settings.hyperliquid_enabled or not self.account_address:
            return None

        data = self._post_json('/info', {'type': 'clearinghouseState', 'user': self.account_address})
        ms = data.get('marginSummary') or {}
        return AccountState(
            venue=self.name,
            equity_usd=float(ms.get('accountValue') or 0.0),
            available_margin_usd=float(ms.get('withdrawable') or 0.0),
            maintenance_margin_usd=float(ms.get('totalMarginUsed') or 0.0),
            venue_payload={'raw': data},
        )

    def fetch_positions(self) -> list[PositionState]:
        if not settings.hyperliquid_enabled or not self.account_address:
            return []

        data = self._post_json('/info', {'type': 'clearinghouseState', 'user': self.account_address})
        out: list[PositionState] = []
        for item in data.get('assetPositions') or []:
            pos = item.get('position') or {}
            szi = float(pos.get('szi') or 0.0)
            if szi == 0:
                continue
            out.append(
                PositionState(
                    strategy_instance_id='venue_account',
                    venue=self.name,
                    market=str(pos.get('coin') or '') + '-PERP',
                    qty=szi,
                    avg_entry_price=float(pos.get('entryPx') or 0.0),
                    realized_pnl_usd=float(pos.get('realizedPnl') or 0.0),
                    unrealized_pnl_usd=float(pos.get('unrealizedPnl') or 0.0),
                    leverage=float((pos.get('leverage') or {}).get('value') or 0.0),
                    liquidation_price=float(pos.get('liquidationPx')) if pos.get('liquidationPx') else None,
                    venue_payload={'raw': pos},
                )
            )
        return out

    def health(self) -> dict:
        return {
            'ok': True,
            'adapter': self.name,
            'environment': self.environment,
            'enabled': bool(settings.hyperliquid_enabled),
            'account_configured': bool(self.account_address),
            'auth_configured': bool(self.signer),
        }
