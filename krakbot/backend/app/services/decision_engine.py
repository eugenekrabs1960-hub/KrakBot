from __future__ import annotations

from datetime import datetime, timezone
import threading
import uuid

from sqlalchemy.orm import Session

from app.api.models import runtime_settings
from app.core.config import settings as cfg
from app.core.profiles import PAPER_V1, LIVE_V1
from app.services.ingest.hyperliquid_market import fetch_market_snapshot
from app.services.ingest.hyperliquid_account import fetch_account_snapshot
from app.services.features.market_features import compute_market_features
from app.services.features.ml_scores import compute_ml_scores
from app.services.features.packet_builder import build_feature_packet
from app.services.models.analyst_runner import analyst_runner
from app.services.policy.gate import evaluate_policy
from app.services.execution.broker_router import get_broker
from app.services.journal.writer import write_cycle
from app.services.wallet_signals import ingest_wallet_events_for_coin, generate_wallet_summary_for_coin
from app.services.news_signals import get_news_summary

_cycle_lock = threading.Lock()


def run_decision_cycle(db: Session) -> dict:
    if not _cycle_lock.acquire(blocking=False):
        return {'items': [], 'status': 'skipped_overlapping_cycle'}

    try:
        mode = runtime_settings.mode.execution_mode
        risk_profile = PAPER_V1 if mode == 'paper' else LIVE_V1

        account = fetch_account_snapshot(cfg.hyperliquid_account_address)
        cands = []
        for coin in runtime_settings.universe.tracked_coins:
            m = fetch_market_snapshot(coin)
            ingest_wallet_events_for_coin(db, coin=coin, market_snapshot=m)
            wallet_summary = generate_wallet_summary_for_coin(db, coin=coin)
            news_summary = get_news_summary(coin, m)
            f = compute_market_features(m)
            s = compute_ml_scores(f)
            rank = 0.45 * s['attention_score'] + 0.35 * s['opportunity_score'] + 0.2 * s['tradability_score']
            cands.append((rank, coin, m, f, s, wallet_summary, news_summary))
        cands.sort(key=lambda x: x[0], reverse=True)

        outputs = []
        broker = get_broker(mode)
        top_n = max(2, min(runtime_settings.universe.max_candidates_per_cycle, 3))
        if cfg.llm_safe_mode:
            top_n = min(top_n, max(1, cfg.llm_safe_mode_max_candidates))

        for rank, coin, m, f, s, wallet_summary, news_summary in cands[:top_n]:
            packet = build_feature_packet(
                coin=coin,
                mode=mode,
                market_snapshot=m,
                features=f,
                ml_scores=s,
                policy_context={
                    'current_open_positions': len([p for p in broker.get_positions() if abs(float(p.get('qty', 0))) >= (cfg.paper_material_position_qty_threshold if mode == 'paper' else 1e-9)]),
                    'max_open_positions': runtime_settings.risk.max_open_positions,
                    'max_notional_per_trade': runtime_settings.risk.max_notional_per_trade,
                    'max_total_notional': runtime_settings.risk.max_total_notional,
                    'cooldown_active': False,
                },
                wallet_summary=wallet_summary,
                news_summary=news_summary,
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
        return {'items': outputs, 'status': 'ok', 'top_n': top_n}
    finally:
        _cycle_lock.release()
