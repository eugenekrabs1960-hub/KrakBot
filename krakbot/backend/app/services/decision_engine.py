from __future__ import annotations

from datetime import datetime, timezone
import threading
import uuid

from sqlalchemy.orm import Session
from sqlalchemy import text

from app.api.models import runtime_settings
from app.core.config import settings as cfg
from app.core.profiles import PAPER_V1, LIVE_V1
from app.services.ingest.hyperliquid_market import fetch_market_snapshot
from app.services.ingest.hyperliquid_account import fetch_account_snapshot
from app.services.features.market_features import compute_market_features
from app.services.features.market_series import persist_market_snapshot, load_market_series, ensure_hyperliquid_history_seed, get_seed_state
from app.services.features.ml_scores import compute_ml_scores
from app.services.features.packet_builder import build_feature_packet
from app.services.models.analyst_runner import analyst_runner
from app.services.policy.gate import evaluate_policy
from app.services.execution.broker_router import get_broker
from app.services.journal.writer import write_cycle
from app.services.wallet_signals import ingest_wallet_events_for_coin, generate_wallet_summary_for_coin
from app.services.news_signals import get_news_summary
from app.services.community_signals import get_community_summary
from app.services.wildcard_universe import resolve_active_universe
from app.services.autonomy.events import emit_event

_cycle_lock = threading.Lock()



def _paper_open_coins_from_execution_records(db: Session) -> set[str]:
    rows = db.execute(text("""
      SELECT (payload->>'symbol') as symbol,
             SUM(CASE WHEN payload->>'status'='filled' THEN
                  CASE WHEN payload->>'action'='short' THEN -COALESCE((payload->>'filled_notional_usd')::float, (payload->>'notional_usd')::float,0)/NULLIF(COALESCE((payload->>'fill_price')::float,1),0)
                       WHEN payload->>'action'='long'  THEN  COALESCE((payload->>'filled_notional_usd')::float, (payload->>'notional_usd')::float,0)/NULLIF(COALESCE((payload->>'fill_price')::float,1),0)
                       ELSE 0 END
                  ELSE 0 END) as net_qty
      FROM execution_records
      WHERE mode='paper'
      GROUP BY 1
    """)).mappings().all()
    out=set()
    for r in rows:
        sym = r.get('symbol')
        if sym and abs(float(r.get('net_qty') or 0.0)) > 1e-9:
            out.add(str(sym).replace('-PERP',''))
    return out




def _paper_open_legs_count_from_execution_records(db: Session) -> int:
    rows = db.execute(text("""
      SELECT (payload->>'symbol') as symbol,
             (payload->>'action') as action,
             COALESCE((payload->>'filled_notional_usd')::float, (payload->>'notional_usd')::float, 0) as notional,
             NULLIF(COALESCE((payload->>'fill_price')::float, 0),0) as fill_price,
             payload->>'status' as status,
             payload->>'created_at' as created_at
      FROM execution_records
      WHERE mode='paper'
      ORDER BY created_at ASC
    """)).mappings().all()

    open_lots: dict[str, list[tuple[str,float]]] = {}
    for r in rows:
        if r.get('status') != 'filled':
            continue
        sym = r.get('symbol')
        px = float(r.get('fill_price') or 0.0)
        notion = float(r.get('notional') or 0.0)
        if not sym or px <= 0 or notion <= 0:
            continue
        side = 'short' if str(r.get('action')) == 'short' else 'long'
        qty = notion / px
        lots = open_lots.setdefault(sym, [])
        opposite = 'short' if side == 'long' else 'long'
        rem = qty
        i = 0
        while i < len(lots) and rem > 1e-12:
            lside,lqty = lots[i]
            if lside != opposite or lqty <= 1e-12:
                i += 1
                continue
            c = min(lqty, rem)
            lqty -= c
            rem -= c
            if lqty <= 1e-12:
                lots.pop(i)
            else:
                lots[i] = (lside,lqty)
                i += 1
        if rem > 1e-12:
            lots.append((side, rem))

    return int(sum(len(v) for v in open_lots.values()))


def run_decision_cycle(db: Session) -> dict:
    if not _cycle_lock.acquire(blocking=False):
        return {'items': [], 'status': 'skipped_overlapping_cycle'}

    try:
        mode = runtime_settings.mode.execution_mode
        risk_profile = PAPER_V1 if mode == 'paper' else LIVE_V1

        account = fetch_account_snapshot(cfg.hyperliquid_account_address)
        cands = []
        universe_state = resolve_active_universe(db, runtime_settings)
        active_coins = universe_state.get('active_coins', runtime_settings.universe.tracked_coins)

        broker = get_broker(mode)
        if mode == 'paper':
            open_coins = _paper_open_coins_from_execution_records(db)
        else:
            open_positions = [p for p in broker.get_positions() if abs(float(p.get('qty', 0))) >= (cfg.paper_material_position_qty_threshold if mode == 'paper' else 1e-9)]
            open_coins = {str(p.get('symbol', '')).replace('-PERP','') for p in open_positions if p.get('symbol')}

        scan_coins = list(dict.fromkeys(list(active_coins) + list(open_coins)))

        for coin in scan_coins:
            m = fetch_market_snapshot(coin)
            seed_state = ensure_hyperliquid_history_seed(db, coin)
            ingest_wallet_events_for_coin(db, coin=coin, market_snapshot=m)
            wallet_summary = generate_wallet_summary_for_coin(db, coin=coin)
            news_summary = get_news_summary(coin, m)
            community_summary = get_community_summary(coin)
            persist_market_snapshot(db, m)
            db.flush()
            series = load_market_series(db, coin, lookback_hours=6)
            f = compute_market_features(m, series=series)
            s = compute_ml_scores(f)

            feature_status = {
                'market_source': m.get('source'),
                'history_seed': seed_state,
                'history_seeded': bool(seed_state.get('seeded')),
                'data_completeness_score': f.get('quality', {}).get('data_completeness_score'),
                'source_health_score': f.get('quality', {}).get('source_health_score'),
                'field_source_map': {
                    'returns_volatility_trend': 'direct_hyperliquid_1m_candles',
                    'derivatives_funding': 'direct_hyperliquid_metaAndAssetCtxs',
                    'derivatives_open_interest': 'direct_hyperliquid_metaAndAssetCtxs_latest_snapshot',
                    'orderbook_proxies': 'approx_from_price_volume_no_l2',
                },
                'degraded': bool((m.get('source') != 'hyperliquid_public') or (float(f.get('quality', {}).get('data_completeness_score') or 0.0) < 0.80) or (not bool(seed_state.get('seeded')))),
                'reason': seed_state.get('degraded_reason') or ('realtime_feature_prerequisites_missing_or_warmup' if ((m.get('source') != 'hyperliquid_public') or (float(f.get('quality', {}).get('data_completeness_score') or 0.0) < 0.80)) else None),
            }
            # community signal influences attention ranking only (never direct trade trigger)
            comm_attention_boost = 0.0
            comm_crowding_penalty = 0.0
            if community_summary:
                comm_attention_boost = 0.05 * float(community_summary.get('trendiness_score') or 0.0)
                comm_crowding_penalty = 0.04 * float(community_summary.get('crowding_risk') or 0.0)

            rank = 0.45 * s['attention_score'] + 0.35 * s['opportunity_score'] + 0.2 * s['tradability_score']
            rank = rank + comm_attention_boost - comm_crowding_penalty
            cands.append((rank, coin, m, f, s, wallet_summary, news_summary, community_summary, feature_status))
        cands.sort(key=lambda x: x[0], reverse=True)

        outputs = []

        # always evaluate existing open-position coins for management
        management = [x for x in cands if x[1] in open_coins]

        # split-lane new-entry selection (conservative deterministic)
        core_set = set(universe_state.get('core_coins', ['BTC', 'ETH', 'SOL']))
        wildcard_set = set([w.get('coin') for w in universe_state.get('wildcards', []) if w.get('coin')])

        ranked_new_core = [x for x in cands if x[1] not in open_coins and x[1] in core_set]
        ranked_new_wild = [x for x in cands if x[1] not in open_coins and x[1] in wildcard_set]

        core_pick = ranked_new_core[:1]
        wild_pick = ranked_new_wild[:1]

        # dedupe while preserving order
        eval_list = []
        seen = set()
        for x in (management + core_pick + wild_pick):
            coin = x[1]
            if coin in seen:
                continue
            seen.add(coin)
            eval_list.append(x)

        for rank, coin, m, f, s, wallet_summary, news_summary, community_summary, feature_status in eval_list:
            packet = build_feature_packet(
                coin=coin,
                mode=mode,
                market_snapshot=m,
                features=f,
                ml_scores=s,
                policy_context={
                    'current_open_positions': len([p for p in broker.get_positions() if abs(float(p.get('qty', 0))) >= (cfg.paper_material_position_qty_threshold if mode == 'paper' else 1e-9)]),
                    'current_open_legs': _paper_open_legs_count_from_execution_records(db) if mode == 'paper' else 0,
                    'symbol_open_position': any((str(p.get('symbol')) == f"{coin}-PERP" and abs(float(p.get('qty',0))) >= (cfg.paper_material_position_qty_threshold if mode == 'paper' else 1e-9)) for p in broker.get_positions()),
                    'max_open_positions': runtime_settings.risk.max_open_positions,
                    'max_open_legs': getattr(runtime_settings.risk, 'max_open_legs', 12),
                    'max_notional_per_trade': runtime_settings.risk.max_notional_per_trade,
                    'max_total_notional': runtime_settings.risk.max_total_notional,
                    'cooldown_active': False,
                },
                wallet_summary=wallet_summary,
                news_summary=news_summary,
                community_summary=community_summary,
                feature_engine_status=feature_status,
            )
            decision = analyst_runner.run(packet)
            policy = evaluate_policy(packet, decision, runtime_settings.mode, risk_profile, cfg)
            bucket_audit = dict(getattr(policy, 'leverage_bucket_audit', None) or {})

            emit_event(
                db,
                entity_type='leverage_bucket',
                entity_id=f"bucket:{packet.packet_id}",
                event_type='decision',
                payload={
                    'change_path': 'risk.leverage_bucket',
                    'old_value': None,
                    'new_value': bucket_audit.get('candidate_bucket'),
                    'reason_code': str(bucket_audit.get('bucket_reason_code') or 'bucket_decision'),
                    'target_mode': mode,
                    'packet_id': packet.packet_id,
                    'policy_decision_id': policy.policy_decision_id,
                    'requested_action': decision.action,
                    'final_action': policy.final_action,
                    'candidate_bucket': bucket_audit.get('candidate_bucket'),
                    'enforced_bucket': bucket_audit.get('enforced_bucket'),
                    'enforced_leverage': bucket_audit.get('enforced_leverage'),
                    'clipped_leverage': bucket_audit.get('clipped_leverage'),
                    'downgrade_reason_code': bucket_audit.get('downgrade_reason_code'),
                    'cap_clip_reason_code': bucket_audit.get('cap_clip_reason_code'),
                    'assigned_leverage_current': bucket_audit.get('assigned_leverage_current'),
                    'conviction_score': bucket_audit.get('conviction_score'),
                    'market_quality_score': bucket_audit.get('market_quality_score'),
                    'caution_flags': bucket_audit.get('caution_flags'),
                    'enforcement_applied': bool(bucket_audit.get('enforcement_applied')),
                },
            )

            execution_record = None
            if policy.final_action == 'allow_trade' and decision.action in {'long', 'short'}:
                side = 'buy' if decision.action == 'long' else 'sell'
                er = broker.place_order(packet.symbol, side, policy.position_sizing.notional_usd or 0.0)
                filled_notional = er.get('notional_usd', policy.position_sizing.notional_usd or 0.0)
                fee_bps = cfg.paper_taker_fee_bps if mode == 'paper' else 0.0
                fee_usd = float(filled_notional or 0.0) * (float(fee_bps) / 10000.0)
                leverage = float(policy.position_sizing.max_leverage or 1.0)
                execution_record = {
                    'execution_id': f"exe_{uuid.uuid4().hex[:12]}",
                    'packet_id': packet.packet_id,
                    'policy_decision_id': policy.policy_decision_id,
                    'mode': mode,
                    'symbol': packet.symbol,
                    'action': decision.action,
                    'notional_usd': policy.position_sizing.notional_usd or 0.0,
                    'status': 'filled' if er.get('accepted') else 'rejected',
                    'fill_price': er.get('fill_price'),
                    'filled_notional_usd': filled_notional,
                    'fee_type': 'taker' if mode == 'paper' else None,
                    'leverage': leverage,
                    'fee_bps': fee_bps,
                    'fee_usd': fee_usd,
                    'broker_order_id': er.get('order_id'),
                    'reason': er.get('reason'),
                    'created_at': datetime.now(timezone.utc),
                    'leverage_bucket': bucket_audit.get('enforced_bucket') if bucket_audit.get('enforced_bucket') is not None else bucket_audit.get('candidate_bucket'),
                    'candidate_bucket': bucket_audit.get('candidate_bucket'),
                    'enforced_bucket': bucket_audit.get('enforced_bucket'),
                    'enforced_leverage': bucket_audit.get('enforced_leverage'),
                    'clipped_leverage': bucket_audit.get('clipped_leverage'),
                    'downgrade_reason_code': bucket_audit.get('downgrade_reason_code'),
                    'cap_clip_reason_code': bucket_audit.get('cap_clip_reason_code'),
                    'bucket_reason_code': bucket_audit.get('bucket_reason_code'),
                    'conviction_score': bucket_audit.get('conviction_score'),
                    'market_quality_score': bucket_audit.get('market_quality_score'),
                    'setup_type': decision.setup_type,
                    'direction': decision.action,
                    'take_profit': getattr(getattr(decision, 'targets', None), 'take_profit_hint', None),
                    'stop_loss': getattr(getattr(decision, 'invalidation', None), 'value', None) if getattr(getattr(decision, 'invalidation', None), 'type', None) == 'price_level' else None,
                    'invalidation': getattr(decision, 'invalidation', None).model_dump() if getattr(decision, 'invalidation', None) is not None else None,
                    'expiry': None,
                    'allocation': {
                        'notional_usd': policy.position_sizing.notional_usd or 0.0,
                        'spending_power_used_usd': policy.position_sizing.notional_usd or 0.0,
                        'allocation_policy': 'existing_notional_policy',
                        'allocation_decoupled_from_bucket': True,
                    },
                    'outcomes': {
                        'outcome_5m_bps': None,
                        'outcome_15m_bps': None,
                        'outcome_1h_bps': None,
                        'realized_pnl_usd': None,
                        'realized_pnl_after_fees_usd': None,
                        'mfe_bps': None,
                        'mae_bps': None,
                        'exit_reason': None,
                    },
                }

            write_cycle(db, packet, decision, policy, execution_record)
            outputs.append({
                'packet': packet.model_dump(),
                'decision': decision.model_dump(),
                'policy': policy.model_dump(),
                'execution': execution_record,
                'account': account,
            })
        return {'items': outputs, 'status': 'ok', 'entry_lanes': {'core': [x[1] for x in core_pick], 'wildcard': [x[1] for x in wild_pick]}, 'management_coins': sorted(list(open_coins)), 'evaluated_coins': [x[1] for x in eval_list], 'universe': universe_state}
    finally:
        _cycle_lock.release()
