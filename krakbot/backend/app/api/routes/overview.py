from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.api.models import runtime_settings
from app.core.database import get_db
from app.models.db_models import WalletSummaryDB, PolicyDecisionDB, ExecutionRecordDB, DecisionOutputDB
from app.services.journal.queries import recent_decisions
from app.services.execution.broker_router import get_broker
from app.services.ingest.hyperliquid_market import fetch_market_snapshot
from app.services.features.market_features import compute_market_features
from app.services.features.ml_scores import compute_ml_scores

router = APIRouter(tags=['overview'])


def _top_candidates_snapshot(db: Session, coins: list[str]) -> list[dict]:
    # pull latest decision/policy context for watch panel
    dec_rows = db.query(DecisionOutputDB).order_by(desc(DecisionOutputDB.generated_at)).limit(300).all()
    latest_dec = {}
    for d in dec_rows:
        p = d.payload or {}
        coin = p.get('coin')
        if coin and coin not in latest_dec:
            latest_dec[coin] = p

    pol_rows = db.query(PolicyDecisionDB).order_by(desc(PolicyDecisionDB.evaluated_at)).limit(300).all()
    latest_pol = {}
    for r in pol_rows:
        p = r.payload or {}
        coin = p.get('coin')
        if coin and coin not in latest_pol:
            latest_pol[coin] = p

    items = []
    for coin in coins:
        m = fetch_market_snapshot(coin)
        f = compute_market_features(m)
        s = compute_ml_scores(f)
        rank = 0.45 * s['attention_score'] + 0.35 * s['opportunity_score'] + 0.2 * s['tradability_score']
        d = latest_dec.get(coin, {})
        p = latest_pol.get(coin, {})
        items.append({
            'coin': coin,
            'symbol': m['symbol'],
            'rank_score': rank,
            'attention': s['attention_score'],
            'opportunity': s['opportunity_score'],
            'tradability': s['tradability_score'],
            'action': d.get('action'),
            'setup_type': d.get('setup_type'),
            'confidence': d.get('confidence'),
            'key_risks': [x.get('label') for x in (d.get('risks') or [])[:2]],
            'policy_result': p.get('final_action'),
        })
    items.sort(key=lambda x: x['rank_score'], reverse=True)
    return items



def _derive_recent_trade_rows(exec_rows: list[dict]) -> tuple[list[dict], float, int, int, float | None]:
    # simplistic paper trade derivation: pair opposite-side fills on same symbol in order
    open_by_symbol: dict[str, dict] = {}
    closed: list[dict] = []

    for e in exec_rows:
        if e.get('status') != 'filled':
            continue
        sym = e.get('symbol')
        if not sym:
            continue
        side = e.get('action')
        ts = e.get('created_at')
        px = float(e.get('fill_price') or 0.0)
        notional = float(e.get('filled_notional_usd') or e.get('notional_usd') or 0.0)

        prev = open_by_symbol.get(sym)
        if prev and prev.get('side') != side:
            entry_px = float(prev.get('entry_price') or 0.0)
            entry_side = prev.get('side')
            if entry_px > 0 and px > 0:
                move = (px / entry_px) - 1.0
                sign = 1.0 if entry_side == 'long' else -1.0
                pnl = sign * move * float(prev.get('notional_usd') or notional)
            else:
                pnl = 0.0
            closed.append({
                'coin': sym.replace('-PERP', ''),
                'symbol': sym,
                'side': entry_side,
                'entry': entry_px,
                'exit': px,
                'pnl': pnl,
                'opened_at': prev.get('opened_at'),
                'closed_at': ts,
                'duration': None,
                'setup_type': prev.get('setup_type'),
            })
            open_by_symbol.pop(sym, None)
        else:
            open_by_symbol[sym] = {
                'symbol': sym,
                'side': side,
                'entry_price': px,
                'notional_usd': notional,
                'opened_at': ts,
                'setup_type': e.get('setup_type'),
            }

    realized = sum(float(x.get('pnl') or 0.0) for x in closed)
    wins = sum(1 for x in closed if float(x.get('pnl') or 0.0) > 0)
    losses = sum(1 for x in closed if float(x.get('pnl') or 0.0) <= 0)
    avg = (realized / len(closed)) if closed else None
    return closed[-20:][::-1], realized, wins, losses, avg


@router.get('/overview')
def overview(db: Session = Depends(get_db)):
    broker = get_broker(runtime_settings.mode.execution_mode)
    decisions = recent_decisions(db, limit=20)

    wallet_items = []
    for coin in runtime_settings.universe.tracked_coins:
        row = (
            db.query(WalletSummaryDB)
            .filter(WalletSummaryDB.coin == coin)
            .order_by(desc(WalletSummaryDB.generated_at))
            .first()
        )
        wallet_items.append({
            'coin': coin,
            'symbol': f'{coin}-PERP',
            'summary': row.payload if row else None,
            'generated_at': row.generated_at if row else None,
        })

    policy_rows = db.query(PolicyDecisionDB).order_by(desc(PolicyDecisionDB.evaluated_at)).limit(120).all()
    allowed = [r.payload for r in policy_rows if (r.payload or {}).get('final_action') == 'allow_trade'][:20]
    blocked = [r.payload for r in policy_rows if str((r.payload or {}).get('final_action', '')).startswith('block_')][:20]
    block_reasons = {}
    for b in blocked:
        k = b.get('downgrade_or_block_reason') or 'unspecified'
        block_reasons[k] = block_reasons.get(k, 0) + 1

    exec_rows_db = db.query(ExecutionRecordDB).order_by(desc(ExecutionRecordDB.created_at)).limit(400).all()

    policy_by_packet = {}
    for r in policy_rows:
        p = r.payload or {}
        pid = p.get('packet_id')
        if pid and pid not in policy_by_packet:
            policy_by_packet[pid] = p

    recent_decision_trace = []
    for d in decisions:
        p = policy_by_packet.get(d.get('packet_id'), {})
        recent_decision_trace.append({
            'timestamp': d.get('generated_at'),
            'coin': d.get('coin'),
            'symbol': d.get('symbol'),
            'action': d.get('action'),
            'setup_type': d.get('setup_type'),
            'confidence': d.get('confidence'),
            'policy_result': p.get('final_action'),
            'reason_summary': [x.get('label') for x in (d.get('reasons') or [])[:2]],
        })
    recent_exec = [r.payload for r in exec_rows_db]

    # positions + unrealized
    pos_raw = broker.get_positions()
    dec_rows = db.query(DecisionOutputDB).order_by(desc(DecisionOutputDB.generated_at)).limit(400).all()
    latest_decision_by_symbol = {}
    for d in dec_rows:
        p = d.payload or {}
        sym = p.get('symbol')
        if sym and sym not in latest_decision_by_symbol:
            latest_decision_by_symbol[sym] = p

    last_fill_by_symbol = {}
    for e in recent_exec:
        sym = e.get('symbol')
        if not sym:
            continue
        if sym not in last_fill_by_symbol and e.get('status') == 'filled':
            last_fill_by_symbol[sym] = e

    open_positions = []
    unrealized_total = 0.0
    for p in pos_raw:
        sym = p.get('symbol')
        qty = float(p.get('qty') or 0.0)
        coin = sym.replace('-PERP', '')
        m = fetch_market_snapshot(coin)
        mark = float(m.get('mark_price') or m.get('last_price') or 0.0)
        fill = last_fill_by_symbol.get(sym, {})
        entry = float(p.get('entry_px') or fill.get('fill_price') or 0.0)
        side = 'long' if qty > 0 else 'short' if qty < 0 else 'flat'
        unreal = 0.0
        if entry > 0 and mark > 0:
            sign = 1 if qty > 0 else -1
            unreal = sign * ((mark / entry) - 1.0) * float(fill.get('filled_notional_usd') or fill.get('notional_usd') or abs(qty) * mark)
        unrealized_total += unreal
        d = latest_decision_by_symbol.get(sym, {})
        open_positions.append({
            'coin': coin,
            'symbol': sym,
            'side': side,
            'qty': qty,
            'entry_price': entry,
            'current_price': mark,
            'unrealized_pnl': unreal,
            'opened_at': fill.get('created_at'),
            'setup_type': d.get('setup_type'),
            'confidence': d.get('confidence'),
            'mode': runtime_settings.mode.execution_mode,
        })

    trades_panel, realized_pnl, wins, losses, avg_pnl = _derive_recent_trade_rows(recent_exec[::-1])

    allowed_count = sum(1 for r in policy_rows if (r.payload or {}).get('final_action') == 'allow_trade')
    blocked_count = sum(1 for r in policy_rows if str((r.payload or {}).get('final_action', '')).startswith('block_'))

    top_candidates = _top_candidates_snapshot(db, runtime_settings.universe.tracked_coins)

    return {
        'mode': runtime_settings.mode.model_dump(),
        'tracked_universe': runtime_settings.universe.model_dump(),
        'open_positions': open_positions,
        'open_positions_count': len(open_positions),
        'recent_decisions': decisions,
        'recent_decision_trace': recent_decision_trace,
        'recent_allowed_trades': allowed,
        'recent_blocked_trades': blocked,
        'dominant_block_reasons': block_reasons,
        'recent_execution': recent_exec[:50],
        'recent_trade_fills': trades_panel,
        'top_candidates': top_candidates,
        'wallet_summaries': wallet_items,
        'last_decision_cycle_at': (policy_rows[0].payload or {}).get('evaluated_at') if policy_rows else None,
        'performance_summary': {
            'realized_pnl': realized_pnl,
            'unrealized_pnl': unrealized_total,
            'total_open_positions': len(open_positions),
            'recent_trade_count': len(trades_panel),
            'allowed_trade_count': allowed_count,
            'blocked_trade_count': blocked_count,
            'win_rate': (wins / (wins + losses)) if (wins + losses) > 0 else None,
            'avg_pnl_per_trade': avg_pnl,
        },
        'recent_pnl_summary': {'realized_pnl_usd': realized_pnl, 'unrealized_pnl_usd': unrealized_total},
    }
