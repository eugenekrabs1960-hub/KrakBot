import json
import time

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.services.eif_regime import EIFRegimeSnapshotBuilder
from app.services.eif_vocab import REASON_CODE_VERSION, TAG_DICTIONARY_VERSION


class EIFCaptureService:
    def __init__(self):
        self._regime_builder = EIFRegimeSnapshotBuilder()

    @property
    def enabled(self) -> bool:
        return settings.eif_capture_enabled

    def capture_filter_decision(
        self,
        db: Session,
        *,
        strategy_instance_id: str,
        market: str,
        event_type: str,
        decision: str,
        reason_code: str,
        allowed: bool,
        tags: list[str] | None = None,
        details: dict | None = None,
        ts_ms: int | None = None,
    ):
        if not self.enabled:
            return

        ts_ms = ts_ms or int(time.time() * 1000)
        regime = self._regime_builder.build(db, market=market, strategy_instance_id=strategy_instance_id)

        db.execute(
            text(
                """
                INSERT INTO eif_regime_snapshots(
                    strategy_instance_id, market, regime_version, trend, volatility, liquidity,
                    session_structure, sample_size, features, captured_ts
                ) VALUES (
                    :sid, :market, :regime_version, :trend, :volatility, :liquidity,
                    :session_structure, :sample_size, CAST(:features AS jsonb), :captured_ts
                )
                """
            ),
            {
                "sid": strategy_instance_id,
                "market": market,
                "regime_version": regime["regime_version"],
                "trend": regime["trend"],
                "volatility": regime["volatility"],
                "liquidity": regime["liquidity"],
                "session_structure": regime["session_structure"],
                "sample_size": regime["sample_size"],
                "features": json.dumps(regime["features"]),
                "captured_ts": regime["captured_ts"],
            },
        )

        db.execute(
            text(
                """
                INSERT INTO eif_filter_decisions(
                    strategy_instance_id, market, event_type, decision, reason_code, allowed,
                    reason_code_version, tags, details, regime_version, regime_snapshot_ts, ts
                ) VALUES (
                    :sid, :market, :event_type, :decision, :reason_code, :allowed,
                    :reason_code_version, CAST(:tags AS jsonb), CAST(:details AS jsonb), :regime_version, :regime_snapshot_ts, :ts
                )
                """
            ),
            {
                "sid": strategy_instance_id,
                "market": market,
                "event_type": event_type,
                "decision": decision,
                "reason_code": reason_code,
                "allowed": bool(allowed),
                "reason_code_version": REASON_CODE_VERSION,
                "tags": json.dumps(tags or []),
                "details": json.dumps(details or {}),
                "regime_version": regime["regime_version"],
                "regime_snapshot_ts": regime["captured_ts"],
                "ts": ts_ms,
            },
        )
        db.commit()

    def capture_trade_context_event(
        self,
        db: Session,
        *,
        strategy_instance_id: str,
        market: str,
        event_type: str,
        side: str | None,
        qty: float | None,
        price: float | None,
        pnl_usd: float | None,
        tags: list[str] | None = None,
        context: dict | None = None,
        ts_ms: int | None = None,
    ):
        if not self.enabled:
            return

        ts_ms = ts_ms or int(time.time() * 1000)
        db.execute(
            text(
                """
                INSERT INTO eif_trade_context_events(
                    strategy_instance_id, market, event_type, side, qty, price, pnl_usd,
                    tags_version, tags, context, ts
                ) VALUES (
                    :sid, :market, :event_type, :side, :qty, :price, :pnl_usd,
                    :tags_version, CAST(:tags AS jsonb), CAST(:context AS jsonb), :ts
                )
                """
            ),
            {
                "sid": strategy_instance_id,
                "market": market,
                "event_type": event_type,
                "side": side,
                "qty": qty,
                "price": price,
                "pnl_usd": pnl_usd,
                "tags_version": TAG_DICTIONARY_VERSION,
                "tags": json.dumps(tags or []),
                "context": json.dumps(context or {}),
                "ts": ts_ms,
            },
        )
        db.commit()


eif_capture = EIFCaptureService()
