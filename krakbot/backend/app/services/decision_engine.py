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
from app.services.features.market_series import persist_market_snapshot, load_market_series
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
                'data_completeness_score': f.get('quality', {}).get('data_completeness_score'),
                'source_health_score': f.get('quality', {}).get('source_health_score'),
                'degraded': bool((m.get('source') != 'hyperliquid_public') or (float(f.get('quality', {}).get('data_completeness_score') or 0.0) < 0.80)),
                'reason': 'realtime_feature_prerequisites_missing_or_warmup' if ((m.get('source') != 'hyperliquid_public') or (float(f.get('quality', {}).get('data_completeness_score') or 0.0) < 0.80)) else None,
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
        new_entry_limit = max(1, min(runtime_settings.universe.max_candidates_per_cycle, 3))
        if cfg.llm_safe_mode:
            new_entry_limit = min(new_entry_limit, max(1, cfg.llm_safe_mode_max_candidates))

        # always evaluate existing open-position coins for management
        management = [x for x in cands if x[1] in open_coins]
        ranked_new = [x for x in cands if x[1] not in open_coins]
        eval_list = management + ranked_new[:new_entry_limit]

        for rank, coin, m, f, s, wallet_summary, news_summary, community_summary, feature_status in eval_list:
            packet = build_feature_packet(
                coin=coin,
                mode=mode,
                market_snapshot=m,
                features=f,
                ml_scores=s,
                policy_context={
                    'current_open_positions': len([p for p in broker.get_positions() if abs(float(p.get('qty', 0))) >= (cfg.paper_material_position_qty_threshold if mode == 'paper' else 1e-9)]),
                    'symbol_open_position': any((str(p.get('symbol')) == f"{coin}-PERP" and abs(float(p.get('qty',0))) >= (cfg.paper_material_position_qty_threshold if mode == 'paper' else 1e-9)) for p in broker.get_positions()),
                    'max_open_positions': runtime_settings.risk.max_open_positions,
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
                }

            write_cycle(db, packet, decision, policy, execution_record)
            outputs.append({
                'packet': packet.model_dump(),
                'decision': decision.model_dump(),
                'policy': policy.model_dump(),
                'execution': execution_record,
                'account': account,
            })
        return {'items': outputs, 'status': 'ok', 'new_entry_limit': new_entry_limit, 'management_coins': sorted(list(open_coins)), 'evaluated_coins': [x[1] for x in eval_list], 'universe': universe_state}
    finally:
        _cycle_lock.release()
