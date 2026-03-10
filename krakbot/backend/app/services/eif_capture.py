import json
import logging
import time
from collections import Counter

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.services.eif_regime import EIFRegimeSnapshotBuilder
from app.services.eif_vocab import (
    FILTER_DECISIONS,
    FILTER_EVENT_TYPES,
    FILTER_REASON_CODES,
    REASON_CODE_VERSION,
    SAFE_FILTER_EVENT_TYPE,
    SAFE_TRADE_EVENT_TYPE,
    SAFE_UNKNOWN_DECISION,
    SAFE_UNKNOWN_REASON_CODE,
    SAFE_UNKNOWN_TAG,
    TAG_DICTIONARY_VERSION,
    TRADE_CONTEXT_EVENT_TYPES,
    TRADE_CONTEXT_TAGS,
)

logger = logging.getLogger(__name__)


class EIFCaptureService:
    def __init__(self):
        self._regime_builder = EIFRegimeSnapshotBuilder()
        self._taxonomy_normalization_counts = Counter()

    @property
    def enabled(self) -> bool:
        return settings.eif_capture_enabled

    def _record_taxonomy_normalization(self, field: str, value: object, normalized: object):
        self._taxonomy_normalization_counts[field] += 1
        logger.warning(
            "eif_taxonomy_normalized field=%s value=%s normalized=%s count=%d",
            field,
            value,
            normalized,
            self._taxonomy_normalization_counts[field],
        )

    def _normalize_filter_payload(self, event_type: str, decision: str, reason_code: str, tags: list[str] | None):
        out_event_type = event_type
        out_decision = decision
        out_reason_code = reason_code

        if out_event_type not in FILTER_EVENT_TYPES:
            self._record_taxonomy_normalization("filter.event_type", out_event_type, SAFE_FILTER_EVENT_TYPE)
            out_event_type = SAFE_FILTER_EVENT_TYPE

        if out_decision not in FILTER_DECISIONS:
            self._record_taxonomy_normalization("filter.decision", out_decision, SAFE_UNKNOWN_DECISION)
            out_decision = SAFE_UNKNOWN_DECISION

        allowed_reason_codes = set(FILTER_REASON_CODES.get(out_event_type, [])) | {SAFE_UNKNOWN_REASON_CODE}
        if out_reason_code not in allowed_reason_codes:
            self._record_taxonomy_normalization("filter.reason_code", out_reason_code, SAFE_UNKNOWN_REASON_CODE)
            out_reason_code = SAFE_UNKNOWN_REASON_CODE

        out_tags = self._normalize_tags(tags)
        return out_event_type, out_decision, out_reason_code, out_tags

    def _normalize_trade_payload(self, event_type: str, tags: list[str] | None):
        out_event_type = event_type
        if out_event_type not in TRADE_CONTEXT_EVENT_TYPES:
            self._record_taxonomy_normalization("trade.event_type", out_event_type, SAFE_TRADE_EVENT_TYPE)
            out_event_type = SAFE_TRADE_EVENT_TYPE
        return out_event_type, self._normalize_tags(tags)

    def _normalize_tags(self, tags: list[str] | None) -> list[str]:
        normalized = []
        allowed = {f"{k}:{v}" for k, values in TRADE_CONTEXT_TAGS.items() for v in values}

        for tag in tags or []:
            if tag in allowed:
                normalized.append(tag)
                continue
            self._record_taxonomy_normalization("tags", tag, SAFE_UNKNOWN_TAG)
            normalized.append(SAFE_UNKNOWN_TAG)

        # preserve order while deduplicating
        return list(dict.fromkeys(normalized))

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
        event_type, decision, reason_code, tags = self._normalize_filter_payload(event_type, decision, reason_code, tags)
        regime = self._regime_builder.build(db, market=market, strategy_instance_id=strategy_instance_id)

        regime_snapshot_id = db.execute(
            text(
                """
                INSERT INTO eif_regime_snapshots(
                    strategy_instance_id, market, regime_version, trend, volatility, liquidity,
                    session_structure, sample_size, features, captured_ts
                ) VALUES (
                    :sid, :market, :regime_version, :trend, :volatility, :liquidity,
                    :session_structure, :sample_size, CAST(:features AS jsonb), :captured_ts
                )
                RETURNING id
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
        ).scalar_one()

        db.execute(
            text(
                """
                INSERT INTO eif_filter_decisions(
                    strategy_instance_id, market, event_type, decision, reason_code, allowed,
                    reason_code_version, tags, details, regime_version, regime_snapshot_id, regime_snapshot_ts, ts
                ) VALUES (
                    :sid, :market, :event_type, :decision, :reason_code, :allowed,
                    :reason_code_version, CAST(:tags AS jsonb), CAST(:details AS jsonb), :regime_version, :regime_snapshot_id, :regime_snapshot_ts, :ts
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
                "regime_snapshot_id": regime_snapshot_id,
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
        event_type, tags = self._normalize_trade_payload(event_type, tags)
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
