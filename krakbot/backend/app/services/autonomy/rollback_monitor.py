from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.core.config import settings
from app.models.db_models import AutonomyPromotionDB, ExecutionRecordDB
from app.services.autonomy.rollback_controller import apply_rollback
from app.services.autonomy.events import emit_event
from app.services.autonomy.cooldown_store import is_in_cooldown, set_cooldown


def _window_summary(db: Session, *, limit: int = 80) -> dict:
    rows = (
        db.query(ExecutionRecordDB)
        .filter(ExecutionRecordDB.mode == 'paper')
        .order_by(desc(ExecutionRecordDB.created_at))
        .limit(max(1, int(limit)))
        .all()
    )
    fills = [r for r in rows if ((r.payload or {}).get('status') == 'filled' or r.status == 'filled')]
    fee = sum(float((r.payload or {}).get('fee_usd') or 0.0) for r in fills)
    notional = sum(float((r.payload or {}).get('filled_notional_usd') or r.filled_notional_usd or 0.0) for r in fills)
    fee_drag_bps = (fee / notional * 10_000) if notional > 0 else 0.0
    return {
        'fills': int(len(fills)),
        'fees_usd': round(float(fee), 6),
        'notional_usd': round(float(notional), 6),
        'fee_drag_bps': round(float(fee_drag_bps), 6),
    }


def rollback_tick(db: Session) -> dict:
    promotions = (
        db.query(AutonomyPromotionDB)
        .filter(AutonomyPromotionDB.status == 'applied', AutonomyPromotionDB.target_mode == 'paper')
        .order_by(desc(AutonomyPromotionDB.created_at))
        .limit(20)
        .all()
    )
    if not promotions:
        return {'ok': True, 'status': 'idle', 'reason': 'no_applied_paper_promotions'}

    out_items = []
    rolled_back = 0
    blocked = 0

    min_obs_fills = int(settings.autonomy_rollback_min_observation_fills or 5)
    eq_drop_thr = float(settings.autonomy_rollback_equity_delta_usd or 15.0)
    fee_drag_thr = float(settings.autonomy_rollback_fee_drag_bps or 8.0)

    obs = _window_summary(db)

    for p in promotions:
        payload = p.payload or {}
        change_path = payload.get('change_path')
        old_value = payload.get('old_value')
        new_value = payload.get('new_value')

        baseline = {
            'fills': int(payload.get('baseline_fills') or 0),
            'fees_usd': float(payload.get('baseline_fees_usd') or 0.0),
            'equity': float(payload.get('baseline_total_equity_usd') or 0.0),
            'fee_drag_bps': float(payload.get('baseline_fee_drag_bps') or 0.0),
        }

        trigger_reason = None
        if obs['fills'] < min_obs_fills:
            emit_event(db, entity_type='rollback', entity_id=f'monitor:{p.promotion_id}', event_type='blocked', severity='warn', payload={
                'promotion_id': p.promotion_id,
                'change_path': change_path,
                'old_value': old_value,
                'new_value': new_value,
                'trigger_reason': 'insufficient_observation_window',
                'reason_code': 'insufficient_observation_window',
                'target_mode': p.target_mode,
                'baseline_window_summary': baseline,
                'observed_window_summary': obs,
            })
            blocked += 1
            out_items.append({'promotion_id': p.promotion_id, 'status': 'blocked', 'trigger_reason': 'insufficient_observation_window'})
            continue

        if change_path and is_in_cooldown(db, change_path=change_path):
            emit_event(db, entity_type='rollback', entity_id=f'monitor:{p.promotion_id}', event_type='blocked', severity='warn', payload={
                'promotion_id': p.promotion_id,
                'change_path': change_path,
                'old_value': old_value,
                'new_value': new_value,
                'trigger_reason': 'rollback_cooldown_active',
                'reason_code': 'rollback_cooldown_active',
                'target_mode': p.target_mode,
                'baseline_window_summary': baseline,
                'observed_window_summary': obs,
            })
            blocked += 1
            out_items.append({'promotion_id': p.promotion_id, 'status': 'blocked', 'trigger_reason': 'rollback_cooldown_active'})
            continue

        # explicit simple triggers
        obs_equity = float(payload.get('observed_total_equity_usd') or baseline['equity'])
        eq_delta = obs_equity - baseline['equity']
        fee_drag_delta = float(obs.get('fee_drag_bps') or 0.0) - float(baseline.get('fee_drag_bps') or 0.0)

        if baseline['equity'] > 0 and eq_delta <= -abs(eq_drop_thr):
            trigger_reason = 'equity_drop'
        elif baseline['fee_drag_bps'] > 0 and fee_drag_delta >= abs(fee_drag_thr):
            trigger_reason = 'fee_drag_spike'

        if not trigger_reason:
            out_items.append({'promotion_id': p.promotion_id, 'status': 'ok', 'trigger_reason': None})
            continue

        emit_event(db, entity_type='rollback', entity_id=f'trigger:{p.promotion_id}', event_type='triggered', severity='warn', payload={
            'promotion_id': p.promotion_id,
            'change_path': change_path,
            'old_value': old_value,
            'new_value': new_value,
            'trigger_reason': trigger_reason,
            'reason_code': trigger_reason,
            'target_mode': p.target_mode,
            'baseline_window_summary': baseline,
            'observed_window_summary': obs,
        })

        rb = apply_rollback(db, p.promotion_id, trigger_reason=trigger_reason)
        if change_path:
            set_cooldown(db, change_path=change_path, reason=trigger_reason)

        emit_event(db, entity_type='rollback', entity_id=rb.rollback_id, event_type='applied', payload={
            'promotion_id': p.promotion_id,
            'change_path': change_path,
            'old_value': old_value,
            'new_value': 'reverted_to_pre_snapshot',
            'trigger_reason': trigger_reason,
            'reason_code': trigger_reason,
            'target_mode': p.target_mode,
            'baseline_window_summary': baseline,
            'observed_window_summary': obs,
        })
        rolled_back += 1
        out_items.append({'promotion_id': p.promotion_id, 'status': 'rolled_back', 'trigger_reason': trigger_reason, 'rollback_id': rb.rollback_id})

    return {
        'ok': True,
        'status': 'ok',
        'rolled_back': rolled_back,
        'blocked': blocked,
        'items': out_items,
        'observed_window_summary': obs,
        'at': datetime.now(timezone.utc).isoformat(),
    }
