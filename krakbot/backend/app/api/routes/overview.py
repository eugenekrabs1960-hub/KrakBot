from __future__ import annotations

from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.api.models import runtime_settings
from app.services.wildcard_universe import resolve_active_universe
from app.core.database import get_db
from app.models.db_models import WalletSummaryDB, PolicyDecisionDB, ExecutionRecordDB, DecisionOutputDB, FeaturePacketDB
from app.services.journal.queries import recent_decisions
from app.services.execution.broker_router import get_broker
from app.services.ingest.hyperliquid_market import fetch_market_snapshot
from app.services.features.market_features import compute_market_features
from app.services.features.ml_scores import compute_ml_scores
from app.services.paper_account import compute_paper_account_from_exec
from app.services.features.market_series import get_seed_state

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





def _paper_open_positions_from_exec(exec_rows: list[dict]) -> list[dict]:
    net: dict[str, float] = {}
    last_fill: dict[str, dict] = {}
    for e in exec_rows:
        if e.get('status') != 'filled':
            continue
        sym = e.get('symbol')
        if not sym:
            continue
        px = float(e.get('fill_price') or 100.0)
        notional = float(e.get('filled_notional_usd') or e.get('notional_usd') or 0.0)
        qty = (notional / px) if px > 0 else 0.0
        if e.get('action') == 'short':
            qty = -qty
        net[sym] = net.get(sym, 0.0) + qty
        last_fill[sym] = e

    out = []
    for sym, qty in net.items():
        if abs(qty) <= 1e-9:
            continue
        f = last_fill.get(sym, {})
        out.append({
            'coin': sym.replace('-PERP', ''),
            'symbol': sym,
            'side': 'long' if qty > 0 else 'short',
            'qty': qty,
            'entry_price': float(f.get('fill_price') or 100.0),
            'current_price': None,
            'unrealized_pnl': 0.0,
            'opened_at': f.get('created_at'),
            'setup_type': None,
            'confidence': None,
            'mode': 'paper',
        })
    return out


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
    universe_state = resolve_active_universe(db, runtime_settings)
    active_coins = universe_state.get('active_coins', runtime_settings.universe.tracked_coins)
    for coin in active_coins:
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

    # latest compact news signals by coin
    fp_rows = db.query(FeaturePacketDB).order_by(desc(FeaturePacketDB.generated_at)).limit(200).all()
    latest_news = {}
    latest_community = {}
    latest_feature_status = {}
    packet_feature_status = {}
    now_utc = datetime.now(timezone.utc)
    for r in fp_rows:
        p = r.payload or {}
        coin = p.get('coin')
        opt = p.get('optional_signals') or {}
        ns = opt.get('news_summary')
        cs = opt.get('community_summary')
        fs = opt.get('feature_engine_status')
        if coin and ns and coin not in latest_news:
            latest_news[coin] = ns
        if coin and cs and coin not in latest_community:
            latest_community[coin] = cs
        if coin and fs and coin not in latest_feature_status:
            latest_feature_status[coin] = fs
            packet_feature_status[coin] = {
                'packet_generated_at': r.generated_at,
                'packet_source': fs.get('market_source'),
                'packet_degraded': bool(fs.get('degraded')),
                'packet_reason': fs.get('reason'),
                'packet_source_health_score': fs.get('source_health_score'),
                'packet_data_completeness_score': fs.get('data_completeness_score'),
            }

    live_source_status = {}
    # live refresh of feature status for active universe coins + explicit packet-vs-live separation
    for coin in active_coins:
        pkt = packet_feature_status.get(coin, {})
        pkt_ts = pkt.get('packet_generated_at')
        pkt_age_sec = None
        if pkt_ts:
            try:
                pkt_age_sec = max(0.0, (now_utc - pkt_ts.astimezone(timezone.utc)).total_seconds())
            except Exception:
                pkt_age_sec = None
        try:
            m_live = fetch_market_snapshot(coin)
            f_live = compute_market_features(m_live)
            live_ts = datetime.now(timezone.utc)
            live_age_sec = max(0.0, (now_utc - live_ts).total_seconds())

            source_now = m_live.get('source')
            degraded_now = bool((source_now != 'hyperliquid_public') or (float(f_live.get('quality', {}).get('data_completeness_score') or 0.0) < 0.80))
            reason_now = ('realtime_feature_prerequisites_missing_or_warmup' if degraded_now else None)

            # stale-but-real: brief live hiccup while recent packet source is still real
            if source_now != 'hyperliquid_public' and pkt.get('packet_source') == 'hyperliquid_public' and (pkt_age_sec is not None and pkt_age_sec <= 180):
                source_now = 'stale_but_real'
                degraded_now = True
                reason_now = 'live_hiccup_using_recent_real_packet'

            latest_feature_status[coin] = {
                'market_source': source_now,
                'data_completeness_score': f_live.get('quality', {}).get('data_completeness_score'),
                'source_health_score': f_live.get('quality', {}).get('source_health_score'),
                'degraded': degraded_now,
                'reason': reason_now,
                'source_detail': m_live.get('source_detail'),
            }
            live_source_status[coin] = {
                'coin': coin,
                'live_source_now': source_now,
                'live_snapshot_at': live_ts,
                'live_snapshot_age_sec': round(live_age_sec, 3),
                'live_degraded': degraded_now,
                'live_reason': reason_now,
                'live_source_detail': m_live.get('source_detail'),
                'packet_source': pkt.get('packet_source'),
                'packet_generated_at': pkt_ts,
                'packet_age_sec': round(pkt_age_sec, 3) if pkt_age_sec is not None else None,
                'packet_degraded': pkt.get('packet_degraded'),
                'packet_reason': pkt.get('packet_reason'),
            }
        except Exception as e:
            live_source_status[coin] = {
                'coin': coin,
                'live_source_now': 'unavailable',
                'live_snapshot_at': None,
                'live_snapshot_age_sec': None,
                'live_degraded': True,
                'live_reason': f'live_snapshot_error:{type(e).__name__}',
                'live_source_detail': str(e),
                'packet_source': pkt.get('packet_source'),
                'packet_generated_at': pkt_ts,
                'packet_age_sec': round(pkt_age_sec, 3) if pkt_age_sec is not None else None,
                'packet_degraded': pkt.get('packet_degraded'),
                'packet_reason': pkt.get('packet_reason'),
            }

    allowed = [r.payload for r in policy_rows if (r.payload or {}).get('final_action') == 'allow_trade'][:20]
    blocked = [r.payload for r in policy_rows if str((r.payload or {}).get('final_action', '')).startswith('block_')][:20]
    block_reasons = {}
    for b in blocked:
        k = b.get('downgrade_or_block_reason') or 'unspecified'
        block_reasons[k] = block_reasons.get(k, 0) + 1

    exec_rows_db = db.query(ExecutionRecordDB).order_by(desc(ExecutionRecordDB.created_at)).all()

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

    paper_account = compute_paper_account_from_exec(recent_exec)

    # positions + unrealized
    dec_rows = db.query(DecisionOutputDB).order_by(desc(DecisionOutputDB.generated_at)).all()
    latest_decision_by_symbol = {}
    for d in dec_rows:
        p = d.payload or {}
        sym = p.get('symbol')
        if sym and sym not in latest_decision_by_symbol:
            latest_decision_by_symbol[sym] = p

    if runtime_settings.mode.execution_mode == 'paper':
        open_positions = _paper_open_positions_from_exec(recent_exec)
        for op in open_positions:
            d = latest_decision_by_symbol.get(op['symbol'], {})
            op['setup_type'] = d.get('setup_type')
            op['confidence'] = d.get('confidence')
        unrealized_total = 0.0
    else:
        pos_raw = broker.get_positions()
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

    top_candidates = _top_candidates_snapshot(db, active_coins)
    degraded = [c for c in latest_feature_status.values() if c.get('degraded')]

    history_seed_status = {coin: get_seed_state(coin) for coin in active_coins}

    return {
        'mode': runtime_settings.mode.model_dump(),
        'tracked_universe': runtime_settings.universe.model_dump(),
        'open_positions': open_positions,
        'open_positions_count': len(open_positions),
        'recent_decisions': decisions,
        'recent_decision_trace': recent_decision_trace,
        'history_seed_status': history_seed_status,
        'recent_allowed_trades': allowed,
        'recent_blocked_trades': blocked,
        'dominant_block_reasons': block_reasons,
        'recent_execution': recent_exec[:50],
        'recent_trade_fills': trades_panel,
        'top_candidates': top_candidates,
        'feature_degraded_count': len(degraded),
        'active_universe': universe_state,
        'trading_universe_status': {
            'core_coins': universe_state.get('core_coins', []),
            'wildcards': universe_state.get('wildcards', []),
            'next_reeval_at': universe_state.get('next_reeval_at'),
            'pinned_open_position_coins': sorted(list({p.get('coin') for p in open_positions if p.get('coin')})),
            'live_source_status': live_source_status,
        },
        'wallet_summaries': wallet_items,
        'latest_news_signals': latest_news,
        'latest_community_signals': latest_community,
        'latest_feature_status': latest_feature_status,
        'last_decision_cycle_at': (policy_rows[0].payload or {}).get('evaluated_at') if policy_rows else None,
        'performance_summary': {
            'realized_pnl': paper_account.get('realized_pnl_usd', realized_pnl) if runtime_settings.mode.execution_mode=='paper' else realized_pnl,
            'unrealized_pnl': paper_account.get('unrealized_pnl_usd', unrealized_total) if runtime_settings.mode.execution_mode=='paper' else unrealized_total,
            'total_open_positions': len(open_positions),
            'recent_trade_count': len(trades_panel),
            'allowed_trade_count': allowed_count,
            'blocked_trade_count': blocked_count,
            'win_rate': (wins / (wins + losses)) if (wins + losses) > 0 else None,
            'avg_pnl_per_trade': avg_pnl,
        },
        'recent_pnl_summary': {'realized_pnl_usd': realized_pnl, 'unrealized_pnl_usd': unrealized_total},
        'paper_account': paper_account,
    }
