from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.models import runtime_settings
from app.services.ingest.hyperliquid_market import fetch_market_snapshot
from app.services.features.market_features import compute_market_features
from app.services.features.ml_scores import compute_ml_scores

router = APIRouter(tags=["candidates"])


@router.get('/candidates')
def list_candidates(db: Session = Depends(get_db)):
    items = []
    for coin in runtime_settings.universe.tracked_coins:
        m = fetch_market_snapshot(coin)
        f = compute_market_features(m)
        s = compute_ml_scores(f)
        rank = 0.45 * s['attention_score'] + 0.35 * s['opportunity_score'] + 0.2 * s['tradability_score']
        items.append({"coin": coin, "symbol": m['symbol'], "rank_score": rank, "ml_scores": s, "market": m})
    items.sort(key=lambda x: x['rank_score'], reverse=True)
    return {"items": items}
