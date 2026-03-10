import logging
import time
from dataclasses import dataclass
from enum import IntEnum
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.services.eif_regime import EIFRegimeSnapshotBuilder

logger = logging.getLogger(__name__)


class RuleStage(IntEnum):
    DATA_INTEGRITY = 0
    HARD_RISK = 1
    SETUP_VALIDITY = 2
    SOFT_QUALITY = 3


@dataclass
class RuleResult:
    rule_id: str
    stage: RuleStage
    passed: bool
    reason_code: str
    measured: dict[str, float | int | str | None]
    thresholds: dict[str, float | int | str | None]


@dataclass
class FilterEvaluation:
    allowed: bool
    reason_code: str
    blocked_stage: str | None
    traces: list[dict[str, Any]]
    shadow_mode: bool
    enforce_mode: bool


class EIFFilterEngine:
    version = "v2"

    def __init__(self):
        self._regime_builder = EIFRegimeSnapshotBuilder()

    def evaluate(self, db: Session, candidate: dict[str, Any], decision: str) -> FilterEvaluation:
        shadow_mode = bool(settings.eif_filter_shadow_mode)
        enforce_mode = bool(settings.eif_filter_enforce_mode) and not shadow_mode

        try:
            metrics = self._load_metrics(db, candidate)
            regime = self._regime_builder.build(db, market=candidate["market"], strategy_instance_id=candidate["strategy_instance_id"])
            rules = self._build_rules(metrics, regime, candidate, decision)
            results = [r() for r in rules]
            failed = sorted([r for r in results if not r.passed], key=lambda r: (r.stage, r.rule_id))
            blocking = failed[0] if failed else None

            would_allow = blocking is None
            allowed = True if (shadow_mode or not enforce_mode) else would_allow
            reason_code = "ok" if (allowed and blocking is None) else (blocking.reason_code if blocking else "ok")
            if allowed and blocking is not None and shadow_mode:
                reason_code = f"shadow_{blocking.reason_code}"

            return FilterEvaluation(
                allowed=bool(allowed),
                reason_code=reason_code,
                blocked_stage=(blocking.stage.name.lower() if blocking else None),
                traces=[
                    {
                        "rule_id": r.rule_id,
                        "stage": r.stage.name.lower(),
                        "passed": r.passed,
                        "reason_code": r.reason_code,
                        "measured": r.measured,
                        "thresholds": r.thresholds,
                    }
                    for r in results
                ],
                shadow_mode=shadow_mode,
                enforce_mode=enforce_mode,
            )
        except Exception as exc:
            logger.exception("eif_filter_engine_eval_error strategy=%s market=%s", candidate.get("strategy_instance_id"), candidate.get("market"))
            fail_closed = bool(settings.eif_filter_fail_closed)
            return FilterEvaluation(
                allowed=not fail_closed,
                reason_code="filter_eval_error",
                blocked_stage="data_integrity",
                traces=[{"rule_id": "engine_error", "stage": "data_integrity", "passed": False, "reason_code": "filter_eval_error", "measured": {"error": str(exc)}, "thresholds": {}}],
                shadow_mode=shadow_mode,
                enforce_mode=enforce_mode,
            )

    def _load_metrics(self, db: Session, candidate: dict[str, Any]) -> dict[str, Any]:
        market = candidate["market"]
        strategy_instance_id = candidate["strategy_instance_id"]
        now_ms = int(time.time() * 1000)

        m = db.execute(
            text(
                """
                WITH recent_trades AS (
                    SELECT event_ts, qty, price
                    FROM market_trades
                    WHERE market = :market
                    ORDER BY event_ts DESC
                    LIMIT 200
                ),
                recent_candles AS (
                    SELECT close, high, low
                    FROM candles
                    WHERE market = :market AND timeframe = '1m'
                    ORDER BY open_ts DESC
                    LIMIT 30
                ),
                latest_ob AS (
                    SELECT bids, asks
                    FROM orderbook_snapshots
                    WHERE market = :market
                    ORDER BY event_ts DESC
                    LIMIT 1
                ),
                loss_streak AS (
                    SELECT COUNT(*)::int AS consecutive_losses
                    FROM (
                      SELECT realized_pnl_usd
                      FROM executions
                      WHERE strategy_instance_id = :sid
                      ORDER BY event_ts DESC
                      LIMIT 20
                    ) x
                    WHERE COALESCE(realized_pnl_usd, 0) < 0
                ),
                recent_dd AS (
                    SELECT COALESCE(MAX(drawdown_pct), 0) AS max_drawdown
                    FROM performance_snapshots
                    WHERE strategy_instance_id = :sid
                      AND ts >= NOW() - INTERVAL '6 hours'
                )
                SELECT
                  (SELECT MAX(event_ts) FROM recent_trades) AS latest_trade_ts,
                  (SELECT COUNT(*)::int FROM recent_trades) AS trade_count_200,
                  (SELECT COALESCE(SUM(qty), 0) FROM recent_trades WHERE event_ts >= :from_5m) AS qty_5m,
                  (SELECT COALESCE(AVG(price), 0) FROM recent_trades) AS avg_trade_price,
                  (SELECT COALESCE(MIN(close), 0) FROM recent_candles) AS min_close_30,
                  (SELECT COALESCE(MAX(close), 0) FROM recent_candles) AS max_close_30,
                  (SELECT COALESCE(AVG(close), 0) FROM recent_candles) AS avg_close_30,
                  (SELECT bids FROM latest_ob) AS bids,
                  (SELECT asks FROM latest_ob) AS asks,
                  (SELECT consecutive_losses FROM loss_streak) AS consecutive_losses,
                  (SELECT max_drawdown FROM recent_dd) AS max_drawdown
                """
            ),
            {"market": market, "sid": strategy_instance_id, "from_5m": now_ms - 5 * 60 * 1000},
        ).mappings().first()
        return dict(m or {})

    def _build_rules(self, metrics: dict[str, Any], regime: dict[str, Any], candidate: dict[str, Any], decision: str):
        return [
            lambda: self._rule_data_staleness(metrics),
            lambda: self._rule_min_activity(metrics),
            lambda: self._rule_spread_cap(metrics),
            lambda: self._rule_volatility_band(metrics),
            lambda: self._rule_depth_min(metrics),
            lambda: self._rule_orderbook_imbalance(metrics, decision),
            lambda: self._rule_regime_strategy_compat(regime, candidate),
            lambda: self._rule_cooldown(metrics),
        ]

    def _rule_data_staleness(self, m: dict[str, Any]) -> RuleResult:
        latest = int(m.get("latest_trade_ts") or 0)
        age_ms = int(time.time() * 1000) - latest if latest > 0 else 10**9
        max_age = settings.eif_filter_max_data_age_ms
        passed = latest > 0 and age_ms <= max_age
        return RuleResult("data_staleness", RuleStage.DATA_INTEGRITY, passed, "data_stale" if not passed else "ok", {"age_ms": age_ms}, {"max_age_ms": max_age})

    def _rule_min_activity(self, m: dict[str, Any]) -> RuleResult:
        qty_5m = float(m.get("qty_5m") or 0.0)
        trades = int(m.get("trade_count_200") or 0)
        passed = qty_5m >= settings.eif_filter_min_qty_5m and trades >= settings.eif_filter_min_trade_count_window
        return RuleResult("min_activity", RuleStage.SETUP_VALIDITY, passed, "min_activity_fail" if not passed else "ok", {"qty_5m": qty_5m, "trade_count": trades}, {"min_qty_5m": settings.eif_filter_min_qty_5m, "min_trade_count": settings.eif_filter_min_trade_count_window})

    def _rule_spread_cap(self, m: dict[str, Any]) -> RuleResult:
        best_bid, best_ask, _, _ = self._extract_book(m)
        mid = ((best_bid + best_ask) / 2.0) if best_bid and best_ask else 0.0
        spread_pct = ((best_ask - best_bid) / mid) if mid > 0 else 1.0
        passed = spread_pct <= settings.eif_filter_max_spread_pct
        return RuleResult("spread_cap", RuleStage.HARD_RISK, passed, "spread_too_wide" if not passed else "ok", {"spread_pct": spread_pct}, {"max_spread_pct": settings.eif_filter_max_spread_pct})

    def _rule_volatility_band(self, m: dict[str, Any]) -> RuleResult:
        min_c = float(m.get("min_close_30") or 0.0)
        max_c = float(m.get("max_close_30") or 0.0)
        avg_c = float(m.get("avg_close_30") or 0.0)
        vol = ((max_c - min_c) / avg_c) if avg_c > 0 else 0.0
        passed = settings.eif_filter_min_volatility_pct <= vol <= settings.eif_filter_max_volatility_pct
        return RuleResult("volatility_band", RuleStage.SETUP_VALIDITY, passed, "volatility_out_of_band" if not passed else "ok", {"volatility_pct": vol}, {"min": settings.eif_filter_min_volatility_pct, "max": settings.eif_filter_max_volatility_pct})

    def _rule_depth_min(self, m: dict[str, Any]) -> RuleResult:
        _, _, bid_depth, ask_depth = self._extract_book(m)
        min_depth = min(bid_depth, ask_depth)
        passed = min_depth >= settings.eif_filter_min_depth_qty
        return RuleResult("liquidity_depth", RuleStage.HARD_RISK, passed, "depth_too_thin" if not passed else "ok", {"bid_depth": bid_depth, "ask_depth": ask_depth}, {"min_depth_qty": settings.eif_filter_min_depth_qty})

    def _rule_orderbook_imbalance(self, m: dict[str, Any], decision: str) -> RuleResult:
        _, _, bid_depth, ask_depth = self._extract_book(m)
        total = bid_depth + ask_depth
        imbalance = ((bid_depth - ask_depth) / total) if total > 0 else 0.0
        threshold = settings.eif_filter_min_imbalance_abs
        passed = True
        if decision == "enter":
            passed = imbalance >= -threshold
        elif decision == "exit":
            passed = imbalance <= threshold
        return RuleResult("orderbook_imbalance", RuleStage.SOFT_QUALITY, passed, "imbalance_direction_mismatch" if not passed else "ok", {"imbalance": imbalance, "decision": decision}, {"max_abs": threshold})

    def _rule_regime_strategy_compat(self, regime: dict[str, Any], candidate: dict[str, Any]) -> RuleResult:
        strategy = (candidate.get("strategy_name") or "").lower()
        trend = regime.get("trend", "unknown")
        volatility = regime.get("volatility", "unknown")
        allowed = True
        if "trend" in strategy and trend == "flat":
            allowed = False
        if "mean" in strategy and volatility == "high":
            allowed = False
        if "breakout" in strategy and volatility == "low":
            allowed = False
        return RuleResult("regime_strategy_compat", RuleStage.SETUP_VALIDITY, allowed, "regime_strategy_mismatch" if not allowed else "ok", {"trend": trend, "volatility": volatility, "strategy": strategy}, {"policy": "trend!=flat, mean!=high_vol, breakout!=low_vol"})

    def _rule_cooldown(self, m: dict[str, Any]) -> RuleResult:
        consecutive_losses = int(m.get("consecutive_losses") or 0)
        max_drawdown = float(m.get("max_drawdown") or 0.0)
        loss_limit = settings.eif_filter_cooldown_consecutive_losses
        dd_limit = settings.eif_filter_drawdown_shock_pct
        passed = consecutive_losses < loss_limit and max_drawdown < dd_limit
        return RuleResult("cooldown_loss_drawdown", RuleStage.HARD_RISK, passed, "cooldown_active" if not passed else "ok", {"consecutive_losses": consecutive_losses, "max_drawdown": max_drawdown}, {"loss_limit": loss_limit, "drawdown_limit": dd_limit})

    def _extract_book(self, m: dict[str, Any]):
        bids = m.get("bids") or []
        asks = m.get("asks") or []
        try:
            best_bid = float(bids[0][0]) if bids else 0.0
            best_ask = float(asks[0][0]) if asks else 0.0
            levels = max(1, int(settings.eif_filter_depth_levels))
            bid_depth = sum(float(x[1]) for x in bids[:levels]) if bids else 0.0
            ask_depth = sum(float(x[1]) for x in asks[:levels]) if asks else 0.0
        except Exception:
            best_bid, best_ask, bid_depth, ask_depth = 0.0, 0.0, 0.0, 0.0
        return best_bid, best_ask, bid_depth, ask_depth


eif_filter_engine = EIFFilterEngine()
