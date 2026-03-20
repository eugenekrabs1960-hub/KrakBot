from __future__ import annotations

from datetime import datetime, timezone, timedelta
import json
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.ingest.hyperliquid_market import fetch_market_snapshot
from app.services.features.market_features import compute_market_features
from app.services.features.ml_scores import compute_ml_scores
from app.services.news_signals import get_news_summary
from app.services.community_signals import get_community_summary

STATE_KEY = 'wildcard_universe_state_v1'


def _now():
    return datetime.now(timezone.utc)


def _parse_dt(s: str | None):
    if not s:
        return None
    try:
        return datetime.fromisoformat(s)
    except Exception:
        return None


def _load_state(db: Session) -> dict:
    row = db.execute(text("SELECT value FROM system_state WHERE key=:k LIMIT 1"), {'k': STATE_KEY}).mappings().first()
    if not row:
        return {}
    v = row.get('value')
    if isinstance(v, dict):
        return v
    try:
        return json.loads(v)
    except Exception:
        return {}


def _save_state(db: Session, state: dict):
    payload = json.dumps(state)
    try:
        db.execute(text("""
            INSERT INTO system_state(key, value, updated_at)
            VALUES (:k, CAST(:p AS jsonb), CURRENT_TIMESTAMP)
            ON CONFLICT (key)
            DO UPDATE SET value=EXCLUDED.value, updated_at=CURRENT_TIMESTAMP
        """), {'k': STATE_KEY, 'p': payload})
    except Exception:
        db.execute(text("""
            INSERT INTO system_state(key, value, updated_at)
            VALUES (:k, :p, CURRENT_TIMESTAMP)
            ON CONFLICT (key)
            DO UPDATE SET value=excluded.value, updated_at=CURRENT_TIMESTAMP
        """), {'k': STATE_KEY, 'p': payload})


def _net_open_symbols(db: Session) -> set[str]:
    rows = db.execute(text("""
      SELECT payload->>'symbol' as symbol,
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
      if r.get('symbol') and abs(float(r.get('net_qty') or 0.0)) > 1e-9:
        out.add(str(r['symbol']))
    return out


def _coin_trade_quality_prior(db: Session, coin: str) -> float:
    rows = db.execute(text("""
      SELECT final_action, COUNT(*) c
      FROM policy_decisions
      WHERE payload->>'coin'=:coin
      GROUP BY final_action
    """), {'coin': coin}).mappings().all()
    m = {r['final_action']: int(r['c']) for r in rows}
    allow = m.get('allow_trade', 0)
    blocks = sum(v for k, v in m.items() if str(k).startswith('block_'))
    total = max(1, allow + blocks)
    return max(0.0, min(1.0, allow / total))


def _wildcard_score(coin: str, market: dict, features: dict, ml: dict, news: dict | None, comm: dict | None, trade_quality: float) -> tuple[float, dict]:
    news_fresh = float((news or {}).get('freshness_score') or 0.0)
    news_rel = min(1.0, ((news or {}).get('headline_count') or 0) / 8.0)
    comm_trend = float((comm or {}).get('trendiness_score') or 0.0)
    comm_heat = float((comm or {}).get('mention_velocity_score') or 0.0)

    tradability = float(ml.get('tradability_score') or 0.0)
    opportunity = float(ml.get('opportunity_score') or 0.0)
    liquidity = float((features.get('quality') or {}).get('liquidity_score') or 0.0)

    crowd = float(ml.get('crowdedness_score') or 0.0)
    frag = float(ml.get('fragility_score') or 0.0)

    score = (
      0.16 * news_fresh +
      0.10 * news_rel +
      0.18 * comm_trend +
      0.08 * comm_heat +
      0.22 * tradability +
      0.16 * opportunity +
      0.10 * trade_quality
    )
    penalty = 0.12 * crowd + 0.08 * frag + 0.10 * max(0.0, 0.35 - liquidity)
    final = max(0.0, min(1.0, score - penalty))
    reason = {
      'news_freshness': news_fresh,
      'community_trend': comm_trend,
      'tradability': tradability,
      'opportunity': opportunity,
      'trade_quality': trade_quality,
      'penalty_crowding': crowd,
      'penalty_fragility': frag,
      'liquidity': liquidity,
      'final': final,
    }
    return final, reason


def resolve_active_universe(db: Session, runtime_settings) -> dict:
    u = runtime_settings.universe
    core = [c.upper() for c in (getattr(u, 'core_coins', None) or ['BTC', 'ETH', 'SOL'])][:3]
    pool = [c.upper() for c in (getattr(u, 'wildcard_pool', None) or []) if c.upper() not in core]
    slots = int(getattr(u, 'wildcard_slots', 2) or 2)
    reeval_min = int(getattr(u, 'wildcard_reeval_minutes', 30) or 30)
    hold_min = int(getattr(u, 'wildcard_min_hold_minutes', 60) or 60)
    threshold = float(getattr(u, 'wildcard_replace_threshold', 0.08) or 0.08)

    state = _load_state(db)
    wildcards = [w.get('coin') for w in state.get('wildcards', []) if w.get('coin')]
    selected_at = state.get('selected_at', {})
    next_eval_at = _parse_dt(state.get('next_eval_at'))

    # bootstrap selection
    if not wildcards:
        wildcards = pool[:slots]
        now = _now().isoformat()
        for c in wildcards:
            selected_at[c] = now
        next_eval_at = _now() + timedelta(minutes=reeval_min)

    should_eval = (next_eval_at is None) or (_now() >= next_eval_at)

    scores = {}
    reasons = {}
    for coin in pool:
        m = fetch_market_snapshot(coin)
        f = compute_market_features(m)
        ml = compute_ml_scores(f)
        n = get_news_summary(coin, m)
        c = get_community_summary(coin)
        tq = _coin_trade_quality_prior(db, coin)
        sc, rs = _wildcard_score(coin, m, f, ml, n, c, tq)
        scores[coin] = sc
        reasons[coin] = rs

    open_syms = _net_open_symbols(db)
    pinned = {s.replace('-PERP', '') for s in open_syms if s}

    if should_eval:
        ranked = sorted(pool, key=lambda c: scores.get(c, 0.0), reverse=True)
        current_set = list(wildcards)
        # protect pinned/open position wildcards from rotation
        rotatable = [c for c in current_set if c not in pinned]
        for cand in ranked:
            if cand in current_set:
                continue
            if len(current_set) < slots:
                current_set.append(cand)
                selected_at[cand] = _now().isoformat()
                continue
            # find weakest rotatable slot that passed min hold
            weakest = None
            weakest_score = 10
            for c in rotatable:
                held_since = _parse_dt(selected_at.get(c)) or _now()
                if (_now() - held_since).total_seconds() < hold_min * 60:
                    continue
                sc = scores.get(c, 0.0)
                if sc < weakest_score:
                    weakest = c
                    weakest_score = sc
            if weakest is None:
                continue
            if scores.get(cand, 0.0) >= weakest_score + threshold:
                current_set[current_set.index(weakest)] = cand
                selected_at[cand] = _now().isoformat()
        wildcards = current_set[:slots]
        next_eval_at = _now() + timedelta(minutes=reeval_min)

    state = {
        'core_coins': core,
        'wildcards': [{'coin': c, 'score': scores.get(c, 0.0), 'reason': reasons.get(c, {})} for c in wildcards],
        'selected_at': selected_at,
        'next_eval_at': next_eval_at.isoformat() if next_eval_at else None,
        'params': {
            'slots': slots,
            'reeval_minutes': reeval_min,
            'min_hold_minutes': hold_min,
            'replace_threshold': threshold,
        },
    }
    _save_state(db, state)

    active = core + [w['coin'] for w in state['wildcards']]
    active = active[: max(3, min(5, len(active)))]
    return {
        'active_coins': active,
        'core_coins': core,
        'wildcards': state['wildcards'],
        'next_reeval_at': state['next_eval_at'],
        'params': state['params'],
    }
