from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import random
import uuid

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.models.db_models import WalletEventDB, WalletSummaryDB


def _seed(coin: str, bucket_ts: int) -> int:
    h = hashlib.sha256(f"{coin}:{bucket_ts}".encode()).hexdigest()[:16]
    return int(h, 16)


def ingest_wallet_events_for_coin(db: Session, coin: str, market_snapshot: dict, now: datetime | None = None) -> list[dict]:
    """Read-only wallet event ingestion stub.

    Uses deterministic pseudo-events scoped to tracked coins to bootstrap the
    wallet-signal pipeline without affecting trading decisions.
    """
    now = now or datetime.now(timezone.utc)
    bucket_ts = int(now.timestamp() // 300)  # 5m bucket
    rnd = random.Random(_seed(coin, bucket_ts))

    # idempotency per coin + bucket
    existing = (
        db.query(WalletEventDB)
        .filter(WalletEventDB.coin == coin, WalletEventDB.bucket_ts == bucket_ts)
        .order_by(desc(WalletEventDB.event_ts))
        .all()
    )
    if existing:
        return [
            {
                "event_id": e.event_id,
                "wallet_address": e.wallet_address,
                "side": e.side,
                "notional_usd": e.notional_usd,
                "event_ts": e.event_ts,
            }
            for e in existing
        ]

    n = 3 + rnd.randint(0, 2)
    out: list[dict] = []
    px = float(market_snapshot.get("mark_price") or market_snapshot.get("last_price") or 1.0)

    for i in range(n):
        side = "buy" if rnd.random() > 0.5 else "sell"
        qty = rnd.uniform(2.0, 35.0)
        notional = max(10.0, qty * px * rnd.uniform(0.001, 0.005))
        evt = WalletEventDB(
            event_id=f"we_{uuid.uuid4().hex[:12]}",
            coin=coin,
            symbol=f"{coin}-PERP",
            wallet_address=f"w_{coin.lower()}_{rnd.randint(1000, 9999)}",
            side=side,
            notional_usd=notional,
            event_ts=now,
            bucket_ts=bucket_ts,
            source="wallet_stub_v1",
            payload={"qty": qty, "ref_price": px, "bucket_ts": bucket_ts, "idx": i},
        )
        db.add(evt)
        out.append(
            {
                "event_id": evt.event_id,
                "wallet_address": evt.wallet_address,
                "side": evt.side,
                "notional_usd": evt.notional_usd,
                "event_ts": evt.event_ts.isoformat(),
            }
        )

    db.commit()
    return out


def generate_wallet_summary_for_coin(db: Session, coin: str, lookback_events: int = 120) -> dict:
    rows = (
        db.query(WalletEventDB)
        .filter(WalletEventDB.coin == coin)
        .order_by(desc(WalletEventDB.event_ts))
        .limit(max(10, lookback_events))
        .all()
    )

    if not rows:
        summary = {
            "coin": coin,
            "net_flow_bias": "neutral",
            "wallet_conviction_score": 0.0,
            "wallet_agreement_score": 0.0,
            "wallet_chasing_risk": 0.0,
            "summary_text": "No wallet events yet for tracked coin.",
            "event_count": 0,
        }
    else:
        buy = sum(r.notional_usd for r in rows if r.side == "buy")
        sell = sum(r.notional_usd for r in rows if r.side == "sell")
        total = buy + sell
        net = buy - sell

        conviction = abs(net) / total if total > 0 else 0.0
        agree = max(buy, sell) / total if total > 0 else 0.0

        recent = rows[: min(20, len(rows))]
        recent_total = sum(r.notional_usd for r in recent)
        older = rows[min(20, len(rows)) :] or rows
        older_avg = sum(r.notional_usd for r in older) / max(1, len(older))
        chasing = min(1.0, (recent_total / max(1.0, older_avg * max(1, len(recent)))) - 1.0)
        chasing = max(0.0, chasing)

        bias = "bullish" if net > total * 0.08 else "bearish" if net < -total * 0.08 else "neutral"
        summary = {
            "coin": coin,
            "net_flow_bias": bias,
            "wallet_conviction_score": round(float(conviction), 4),
            "wallet_agreement_score": round(float(agree), 4),
            "wallet_chasing_risk": round(float(chasing), 4),
            "summary_text": f"{coin}: {bias} wallet flow, conviction={conviction:.2f}, agreement={agree:.2f}, chasing_risk={chasing:.2f}",
            "event_count": len(rows),
        }

    row = WalletSummaryDB(
        summary_id=f"ws_{uuid.uuid4().hex[:12]}",
        coin=coin,
        symbol=f"{coin}-PERP",
        generated_at=datetime.now(timezone.utc),
        payload=summary,
    )
    db.add(row)
    db.commit()
    return summary


def latest_wallet_summary_map(db: Session, coins: list[str]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for coin in coins:
        row = (
            db.query(WalletSummaryDB)
            .filter(WalletSummaryDB.coin == coin)
            .order_by(desc(WalletSummaryDB.generated_at))
            .first()
        )
        if row:
            out[coin] = row.payload
    return out
