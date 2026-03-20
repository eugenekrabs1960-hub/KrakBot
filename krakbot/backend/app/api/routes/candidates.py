from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.core.database import get_db
from app.api.models import runtime_settings
from app.services.wildcard_universe import resolve_active_universe
from app.models.db_models import WalletSummaryDB, DecisionOutputDB, PolicyDecisionDB, FeaturePacketDB
from app.services.ingest.hyperliquid_market import fetch_market_snapshot
from app.services.features.market_features import compute_market_features
from app.services.features.ml_scores import compute_ml_scores

router = APIRouter(tags=["candidates"])


def _latest_decision_for_coin(db: Session, coin: str):
    rows = (
        db.query(DecisionOutputDB)
        .order_by(desc(DecisionOutputDB.generated_at))
        .limit(200)
        .all()
    )
    for r in rows:
        p = r.payload or {}
        if p.get("coin") == coin:
            return p
    return None


def _latest_policy_for_coin(db: Session, coin: str):
    rows = (
        db.query(PolicyDecisionDB)
        .order_by(desc(PolicyDecisionDB.evaluated_at))
        .limit(200)
        .all()
    )
    for r in rows:
        p = r.payload or {}
        if p.get("coin") == coin:
            return p
    return None


def _latest_packet_for_coin(db: Session, coin: str):
    row = (
        db.query(FeaturePacketDB)
        .filter(FeaturePacketDB.coin == coin)
        .order_by(desc(FeaturePacketDB.generated_at))
        .first()
    )
    return row.payload if row else None


@router.get('/candidates')
def list_candidates(db: Session = Depends(get_db)):
    wallet_map = {}
    universe_state = resolve_active_universe(db, runtime_settings)
    active_coins = universe_state.get('active_coins', runtime_settings.universe.tracked_coins)
    for coin in active_coins:
        ws = (
            db.query(WalletSummaryDB)
            .filter(WalletSummaryDB.coin == coin)
            .order_by(desc(WalletSummaryDB.generated_at))
            .first()
        )
        if ws:
            wallet_map[coin] = ws.payload

    items = []
    for coin in active_coins:
        m = fetch_market_snapshot(coin)
        f = compute_market_features(m)
        s = compute_ml_scores(f)
        rank = 0.45 * s['attention_score'] + 0.35 * s['opportunity_score'] + 0.2 * s['tradability_score']

        decision = _latest_decision_for_coin(db, coin)
        policy = _latest_policy_for_coin(db, coin)
        packet = _latest_packet_for_coin(db, coin)

        items.append({
            "coin": coin,
            "symbol": m['symbol'],
            "rank_score": rank,
            "ml_scores": s,
            "market": m,
            "wallet_summary": wallet_map.get(coin),
            "latest_decision": {
                "action": (decision or {}).get("action"),
                "setup_type": (decision or {}).get("setup_type"),
                "confidence": (decision or {}).get("confidence"),
                "reasons": (decision or {}).get("reasons", []),
                "risks": (decision or {}).get("risks", []),
            },
            "latest_policy": {
                "final_action": (policy or {}).get("final_action"),
                "block_reason": (policy or {}).get("downgrade_or_block_reason"),
            },
            "packet_context": {
                "contradiction_score": ((packet or {}).get("ml_scores") or {}).get("contradiction_score"),
                "extension_score": ((packet or {}).get("ml_scores") or {}).get("extension_score"),
                "trade_quality_prior": ((packet or {}).get("ml_scores") or {}).get("trade_quality_prior"),
                "regime_compatibility_score": ((packet or {}).get("ml_scores") or {}).get("regime_compatibility_score"),
                "change_summary": (packet or {}).get("change_summary"),
            },
        })
    items.sort(key=lambda x: x['rank_score'], reverse=True)
    return {"items": items}
