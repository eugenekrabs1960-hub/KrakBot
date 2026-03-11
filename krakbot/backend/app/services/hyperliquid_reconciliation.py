from __future__ import annotations

import hashlib
import json
import time

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.adapters.execution.hyperliquid_adapter import HyperliquidExecutionAdapter
from app.services.checkpoints import load_checkpoint, save_checkpoint


class HyperliquidReconciliationService:
    def __init__(self, adapter: HyperliquidExecutionAdapter | None = None):
        self.adapter = adapter or HyperliquidExecutionAdapter()

    def _snapshot_hash(self, account: dict | None, positions: list[dict]) -> str:
        payload = {
            'account': account or {},
            'positions': sorted(positions, key=lambda x: (x.get('market', ''), float(x.get('qty', 0)))),
        }
        canon = json.dumps(payload, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(canon.encode('utf-8')).hexdigest()

    def run_once(self, db: Session):
        account_obj = self.adapter.fetch_account_state()
        positions_obj = self.adapter.fetch_positions()

        account = account_obj.__dict__ if account_obj else None
        positions = [p.__dict__ for p in positions_obj]

        snap_hash = self._snapshot_hash(account, positions)
        prev = load_checkpoint(db, 'hyperliquid_reconciliation_snapshot') or {}
        prev_hash = prev.get('snapshot_hash') if isinstance(prev, dict) else None
        changed = bool(prev_hash and prev_hash != snap_hash)

        details = {
            'changed_since_last': changed,
            'previous_hash': prev_hash,
            'snapshot_hash': snap_hash,
            'positions_count': len(positions),
            'account_equity_usd': (account or {}).get('equity_usd'),
        }
        status = 'drift_detected' if changed else 'ok'
        now_ms = int(time.time() * 1000)

        db.execute(
            text(
                """
                INSERT INTO reconciliations(strategy_instance_id, kind, status, details, ts)
                VALUES (NULL, 'hyperliquid_state', :status, CAST(:details AS jsonb), :ts)
                """
            ),
            {'status': status, 'details': json.dumps(details), 'ts': now_ms},
        )
        db.commit()

        save_checkpoint(
            db,
            'hyperliquid_reconciliation_snapshot',
            {'snapshot_hash': snap_hash, 'ts': now_ms, 'positions_count': len(positions)},
        )

        return {
            'ok': True,
            'status': status,
            'details': details,
            'account': account,
            'positions': positions,
        }
