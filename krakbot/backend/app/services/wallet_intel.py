from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings


CLASS_RULE_VERSION = "wclass-v1"
INFERENCE_VERSION = "winfer-v1"
ELIGIBILITY_VERSION = "welig-v1"
SCORE_VERSION = "wscore-v1"
COHORT_VERSION = "wcohort-v1"
SIGNAL_VERSION = "wsignal-v1"


@dataclass
class EligibilityConfig:
    min_t1_events_30d: int = settings.wallet_intel_min_t1_events_30d
    min_active_days_30d: int = settings.wallet_intel_min_active_days_30d
    min_notional_30d: float = settings.wallet_intel_min_notional_30d
    min_sol_relevance: float = settings.wallet_intel_min_sol_relevance
    recency_days: int = settings.wallet_intel_recency_days


class WalletIntelService:
    def ensure_wallet(self, db: Session, *, chain: str, address: str) -> str:
        wallet_id = f"w_{chain}_{address}"
        db.execute(
            text(
                """
                INSERT INTO wallet_master(id, chain, address)
                VALUES (:id, :chain, :address)
                ON CONFLICT (chain, address) DO NOTHING
                """
            ),
            {"id": wallet_id, "chain": chain, "address": address},
        )
        db.commit()
        return wallet_id

    def ingest_raw_event(self, db: Session, *, wallet_id: str, provider: str, provider_event_id: str, chain: str, event_ts: int, payload: dict):
        raw_id = f"raw_{uuid.uuid4().hex[:12]}"
        db.execute(
            text(
                """
                INSERT INTO wallet_raw_event(id, wallet_id, provider, provider_event_id, chain, event_ts, ingest_ts, payload_json, schema_version)
                VALUES (:id, :wallet_id, :provider, :provider_event_id, :chain, :event_ts, :ingest_ts, CAST(:payload AS jsonb), :schema_version)
                """
            ),
            {
                "id": raw_id,
                "wallet_id": wallet_id,
                "provider": provider,
                "provider_event_id": provider_event_id,
                "chain": chain,
                "event_ts": event_ts,
                "ingest_ts": int(time.time() * 1000),
                "payload": json.dumps(payload),
                "schema_version": "provider-raw-v1",
            },
        )
        db.commit()
        return raw_id

    def normalize_event(self, db: Session, *, wallet_id: str, raw_id: str, event_ts: int, payload: dict):
        can_id = f"can_{uuid.uuid4().hex[:12]}"
        side_hint = payload.get("side_hint", "unknown")
        qty = float(payload.get("qty", 0.0))
        price_ref = float(payload.get("price_ref", 0.0))
        notional = qty * price_ref
        db.execute(
            text(
                """
                INSERT INTO wallet_canonical_event(
                    id, wallet_id, chain, source_raw_event_id, event_type, asset_symbol, quote_symbol,
                    direction_hint, qty, notional_usd_est, event_ts, canonical_version
                ) VALUES (
                    :id, :wallet_id, 'solana', :raw_id, :event_type, :asset, :quote,
                    :direction_hint, :qty, :notional, :event_ts, :canonical_version
                )
                """
            ),
            {
                "id": can_id,
                "wallet_id": wallet_id,
                "raw_id": raw_id,
                "event_type": payload.get("kind", "unknown"),
                "asset": payload.get("asset", "SOL"),
                "quote": "USD",
                "direction_hint": side_hint,
                "qty": qty,
                "notional": notional,
                "event_ts": event_ts,
                "canonical_version": "wcanon-v1",
            },
        )
        db.commit()
        return can_id

    def infer_event(self, db: Session, *, wallet_id: str, canonical_id: str, event_ts: int, payload: dict):
        inf_id = f"inf_{uuid.uuid4().hex[:12]}"
        side_hint = payload.get("side_hint", "unknown")
        qty = float(payload.get("qty", 0.0))
        price_ref = float(payload.get("price_ref", 0.0))
        notional = qty * price_ref

        if payload.get("asset", "SOL") != "SOL":
            tier, score, reasons = "T3", 0.2, ["non_sol_scope"]
        elif payload.get("kind") == "swap" and side_hint in {"buy", "sell"} and notional >= 50:
            tier, score, reasons = "T1", 0.92, ["swap_semantics", "directional_side", "notional_ok"]
        elif side_hint in {"buy", "sell"}:
            tier, score, reasons = "T2", 0.6, ["directional_but_ambiguous"]
        else:
            tier, score, reasons = "T3", 0.25, ["unknown_direction"]

        side = "buy_like" if side_hint == "buy" else "sell_like" if side_hint == "sell" else "unknown"

        db.execute(
            text(
                """
                INSERT INTO wallet_inferred_event(
                    id, wallet_id, canonical_event_id, side, asset_scope, confidence_tier,
                    confidence_score, notional_usd_est, price_ref, event_ts, inference_version, reason_codes
                ) VALUES (
                    :id, :wallet_id, :canonical_id, :side, 'SOL', :tier,
                    :confidence_score, :notional, :price_ref, :event_ts, :inference_version, CAST(:reasons AS jsonb)
                )
                """
            ),
            {
                "id": inf_id,
                "wallet_id": wallet_id,
                "canonical_id": canonical_id,
                "side": side,
                "tier": tier,
                "confidence_score": score,
                "notional": notional,
                "price_ref": price_ref,
                "event_ts": event_ts,
                "inference_version": INFERENCE_VERSION,
                "reasons": json.dumps(reasons),
            },
        )
        db.commit()
        return inf_id

    def classify_wallets(self, db: Session, *, run_id: str, now_ms: int):
        rows = db.execute(
            text(
                """
                SELECT wm.id AS wallet_id,
                       wm.manual_force_exclude AS manual_force_exclude,
                       wm.manual_force_include AS manual_force_include,
                       COUNT(*) FILTER (WHERE wie.confidence_tier='T1') AS t1_count,
                       COALESCE(SUM(wie.notional_usd_est) FILTER (WHERE wie.confidence_tier='T1'),0) AS t1_notional
                FROM wallet_master wm
                LEFT JOIN wallet_inferred_event wie ON wie.wallet_id = wm.id
                GROUP BY wm.id, wm.manual_force_exclude, wm.manual_force_include
                """
            )
        ).mappings().all()

        for r in rows:
            wallet_id = r["wallet_id"]
            t1 = int(r["t1_count"] or 0)
            notion = float(r["t1_notional"] or 0.0)
            label = "unknown"
            excluded = False
            conf = 0.5
            reasons = []
            if bool(r["manual_force_exclude"]):
                label = "unknown"
                excluded = True
                conf = 1.0
                reasons = ["manual_force_exclude"]
            elif bool(r["manual_force_include"]):
                label = "smart_money_candidate"
                conf = 1.0
                reasons = ["manual_force_include"]
            elif t1 >= 20 and notion >= 25000:
                label = "smart_money_candidate"
                conf = 0.8
                reasons = ["t1_count_high", "notional_high"]
            elif t1 >= 5:
                label = "active_speculator"
                conf = 0.7
                reasons = ["activity_detected"]
            else:
                label = "inactive"
                conf = 0.7
                reasons = ["low_activity"]

            db.execute(
                text(
                    """
                    INSERT INTO wallet_classification(wallet_id, class_label, confidence_score, excluded, reason_codes, rule_version, effective_from)
                    VALUES (:wallet_id, :label, :conf, :excluded, CAST(:reasons AS jsonb), :rule_version, :effective_from)
                    """
                ),
                {
                    "wallet_id": wallet_id,
                    "label": label,
                    "conf": conf,
                    "excluded": excluded,
                    "reasons": json.dumps(reasons),
                    "rule_version": CLASS_RULE_VERSION,
                    "effective_from": now_ms,
                },
            )
        db.commit()

    def compute_eligibility(self, db: Session, *, run_id: str, now_ms: int, cfg: EligibilityConfig | None = None):
        cfg = cfg or EligibilityConfig()
        since_30d = now_ms - 30 * 24 * 60 * 60 * 1000
        recency_since = now_ms - cfg.recency_days * 24 * 60 * 60 * 1000

        rows = db.execute(
            text(
                """
                WITH latest_cls AS (
                  SELECT DISTINCT ON (wallet_id) wallet_id, class_label, excluded
                  FROM wallet_classification
                  ORDER BY wallet_id, effective_from DESC
                )
                SELECT wm.id AS wallet_id,
                       wm.manual_force_include AS manual_force_include,
                       wm.manual_force_exclude AS manual_force_exclude,
                       COUNT(*) FILTER (WHERE wie.confidence_tier='T1' AND wie.event_ts >= :since_30d) AS t1_count_30d,
                       COUNT(DISTINCT to_timestamp(wie.event_ts/1000)::date) FILTER (WHERE wie.confidence_tier='T1' AND wie.event_ts >= :since_30d) AS active_days_30d,
                       COALESCE(SUM(wie.notional_usd_est) FILTER (WHERE wie.confidence_tier='T1' AND wie.event_ts >= :since_30d),0) AS notional_30d,
                       COUNT(*) FILTER (WHERE wie.event_ts >= :since_30d) AS all_events_30d,
                       COUNT(*) FILTER (WHERE wie.asset_scope='SOL' AND wie.event_ts >= :since_30d) AS sol_events_30d,
                       COUNT(*) FILTER (WHERE wie.confidence_tier='T1' AND wie.event_ts >= :recency_since) AS t1_recent,
                       COALESCE(lc.excluded, FALSE) AS excluded
                FROM wallet_master wm
                LEFT JOIN wallet_inferred_event wie ON wie.wallet_id = wm.id
                LEFT JOIN latest_cls lc ON lc.wallet_id = wm.id
                GROUP BY wm.id, wm.manual_force_include, wm.manual_force_exclude, lc.excluded
                """
            ),
            {"since_30d": since_30d, "recency_since": recency_since},
        ).mappings().all()

        for r in rows:
            failed = []
            t1 = int(r["t1_count_30d"] or 0)
            ad = int(r["active_days_30d"] or 0)
            notion = float(r["notional_30d"] or 0.0)
            all_events = int(r["all_events_30d"] or 0)
            sol_events = int(r["sol_events_30d"] or 0)
            t1_recent = int(r["t1_recent"] or 0)
            excluded = bool(r["excluded"]) or bool(r["manual_force_exclude"])
            force_include = bool(r["manual_force_include"])
            sol_rel = (sol_events / all_events) if all_events > 0 else 0.0

            if not force_include:
                if t1 < cfg.min_t1_events_30d:
                    failed.append("min_t1_events")
                if ad < cfg.min_active_days_30d:
                    failed.append("min_active_days")
                if notion < cfg.min_notional_30d:
                    failed.append("min_notional")
                if sol_rel < cfg.min_sol_relevance:
                    failed.append("min_sol_relevance")
                if t1_recent < 1:
                    failed.append("recency")
            if excluded:
                failed.append("classification_excluded")

            eligible = (len(failed) == 0) or (force_include and not excluded)
            metrics = {
                "t1_count_30d": t1,
                "active_days_30d": ad,
                "notional_30d": notion,
                "sol_relevance_30d": sol_rel,
                "t1_recent": t1_recent,
            }

            db.execute(
                text(
                    """
                    INSERT INTO wallet_eligibility_snapshot(wallet_id, lookback_days, eligible, failed_rules, metrics_json, threshold_version, generated_at, run_id)
                    VALUES (:wallet_id, 30, :eligible, CAST(:failed_rules AS jsonb), CAST(:metrics_json AS jsonb), :threshold_version, :generated_at, :run_id)
                    """
                ),
                {
                    "wallet_id": r["wallet_id"],
                    "eligible": eligible,
                    "failed_rules": json.dumps(failed),
                    "metrics_json": json.dumps(metrics),
                    "threshold_version": ELIGIBILITY_VERSION,
                    "generated_at": now_ms,
                    "run_id": run_id,
                },
            )
        db.commit()

    def compute_scores(self, db: Session, *, run_id: str, now_ms: int):
        rows = db.execute(
            text(
                """
                WITH latest_elig AS (
                  SELECT DISTINCT ON (wallet_id) wallet_id, eligible, metrics_json
                  FROM wallet_eligibility_snapshot
                  ORDER BY wallet_id, generated_at DESC
                )
                SELECT wm.id AS wallet_id,
                       le.eligible,
                       COALESCE((le.metrics_json->>'t1_count_30d')::int, 0) AS t1_count_30d,
                       COALESCE((le.metrics_json->>'active_days_30d')::int, 0) AS active_days_30d,
                       COALESCE((le.metrics_json->>'notional_30d')::double precision, 0) AS notional_30d,
                       AVG(CASE WHEN wie.side='buy_like' THEN 1 WHEN wie.side='sell_like' THEN -1 ELSE 0 END) FILTER (WHERE wie.confidence_tier='T1') AS directional_mean
                FROM wallet_master wm
                LEFT JOIN latest_elig le ON le.wallet_id = wm.id
                LEFT JOIN wallet_inferred_event wie ON wie.wallet_id = wm.id
                GROUP BY wm.id, le.eligible, le.metrics_json
                """
            )
        ).mappings().all()

        for r in rows:
            if not bool(r["eligible"]):
                continue
            t1 = float(r["t1_count_30d"] or 0)
            act = float(r["active_days_30d"] or 0)
            notion = float(r["notional_30d"] or 0)
            dm = float(r["directional_mean"] or 0)

            performance = min(100.0, 35.0 + min(25.0, abs(dm) * 40.0))
            consistency = min(100.0, 30.0 + min(40.0, act * 2.0))
            reliability = min(100.0, 30.0 + min(30.0, t1 * 0.8))
            asset_rel = 100.0
            conviction = min(100.0, 20.0 + min(40.0, notion / 1500.0))
            stability = min(100.0, 40.0 + min(30.0, t1 * 0.5))
            penalty_sparse = 15.0 if t1 < 30 else 0.0

            total = (
                0.28 * performance
                + 0.17 * consistency
                + 0.15 * reliability
                + 0.12 * asset_rel
                + 0.14 * conviction
                + 0.14 * stability
                - penalty_sparse
            )
            total = max(0.0, min(100.0, total))

            components = {
                "performance": performance,
                "consistency": consistency,
                "reliability": reliability,
                "asset_relevance": asset_rel,
                "conviction": conviction,
                "stability": stability,
            }
            penalties = {"sparse_penalty": penalty_sparse}

            for window in (7, 30, 90):
                db.execute(
                    text(
                        """
                        INSERT INTO wallet_score_snapshot(wallet_id, window_days, score_total, component_scores, penalties_json, score_version, generated_at, run_id)
                        VALUES (:wallet_id, :window_days, :score_total, CAST(:component_scores AS jsonb), CAST(:penalties_json AS jsonb), :score_version, :generated_at, :run_id)
                        """
                    ),
                    {
                        "wallet_id": r["wallet_id"],
                        "window_days": window,
                        "score_total": total,
                        "component_scores": json.dumps(components),
                        "penalties_json": json.dumps(penalties),
                        "score_version": SCORE_VERSION,
                        "generated_at": now_ms,
                        "run_id": run_id,
                    },
                )
        db.commit()

    def build_cohort_and_signal(self, db: Session, *, run_id: str, now_ms: int, cohort_id: str = "top_sol_active_wallets", target_size: int | None = None):
        target_size = target_size or settings.wallet_intel_cohort_target_size
        buffer = settings.wallet_intel_cohort_hysteresis_buffer

        ranked = db.execute(
            text(
                """
                WITH latest_score AS (
                  SELECT DISTINCT ON (wallet_id) wallet_id, score_total
                  FROM wallet_score_snapshot
                  WHERE window_days = 30
                  ORDER BY wallet_id, generated_at DESC
                )
                SELECT wallet_id, score_total
                FROM latest_score
                ORDER BY score_total DESC, wallet_id
                LIMIT :rank_limit
                """
            ),
            {"rank_limit": target_size + buffer},
        ).mappings().all()

        if not ranked:
            return {"cohort_id": cohort_id, "members": 0, "signal": "neutral", "confidence": 0.0}

        prev_members = db.execute(
            text(
                """
                SELECT wallet_id
                FROM wallet_cohort_membership
                WHERE cohort_id=:cohort_id
                  AND cohort_version = (
                    SELECT cohort_version FROM wallet_cohort_snapshot
                    WHERE cohort_id=:cohort_id
                    ORDER BY as_of_ts DESC
                    LIMIT 1
                  )
                """
            ),
            {"cohort_id": cohort_id},
        ).mappings().all()
        prev_set = {r["wallet_id"] for r in prev_members}

        primary = ranked[:target_size]
        reserve = ranked[target_size:target_size + buffer]
        selected = {r["wallet_id"]: float(r["score_total"]) for r in primary}

        for r in reserve:
            wid = r["wallet_id"]
            if wid in prev_set and wid not in selected and len(selected) < target_size:
                selected[wid] = float(r["score_total"])

        # If hysteresis retention did not trigger enough, fill by strict rank.
        if len(selected) < target_size:
            for r in ranked:
                wid = r["wallet_id"]
                if wid not in selected:
                    selected[wid] = float(r["score_total"])
                if len(selected) >= target_size:
                    break

        scores = [{"wallet_id": k, "score_total": v} for k, v in selected.items()]
        scores.sort(key=lambda x: (-x["score_total"], x["wallet_id"]))

        cohort_version = f"{COHORT_VERSION}-{now_ms}"
        for idx, r in enumerate(scores, start=1):
            reason = "retained_hysteresis" if (r["wallet_id"] in prev_set and idx > target_size - buffer) else "selected_ranked"
            db.execute(
                text(
                    """
                    INSERT INTO wallet_cohort_membership(cohort_id, cohort_version, wallet_id, rank, score_total, as_of_ts, reason_json)
                    VALUES (:cohort_id, :cohort_version, :wallet_id, :rank, :score_total, :as_of_ts, CAST(:reason_json AS jsonb))
                    """
                ),
                {
                    "cohort_id": cohort_id,
                    "cohort_version": cohort_version,
                    "wallet_id": r["wallet_id"],
                    "rank": idx,
                    "score_total": float(r["score_total"]),
                    "as_of_ts": now_ms,
                    "reason_json": json.dumps({"selected_from": reason}),
                },
            )

        # Bias from latest T1 inferred events in cohort.
        bias_row = db.execute(
            text(
                """
                SELECT AVG(CASE WHEN wie.side='buy_like' THEN 1 WHEN wie.side='sell_like' THEN -1 ELSE 0 END) AS dm,
                       COUNT(*) FILTER (WHERE wie.confidence_tier='T1') AS n
                FROM wallet_inferred_event wie
                JOIN wallet_cohort_membership wcm ON wcm.wallet_id = wie.wallet_id
                WHERE wcm.cohort_id = :cohort_id
                  AND wcm.cohort_version = :cohort_version
                """
            ),
            {"cohort_id": cohort_id, "cohort_version": cohort_version},
        ).mappings().first()

        dm = float((bias_row or {}).get("dm") or 0.0)
        n = int((bias_row or {}).get("n") or 0)
        bias_state = "neutral"
        if dm > 0.15:
            bias_state = "bullish"
        elif dm < -0.15:
            bias_state = "bearish"

        bias_strength = min(100.0, abs(dm) * 100.0)
        breadth = min(100.0, (n / max(1, len(scores) * 5)) * 100.0)
        concentration = max(0.0, 100.0 - min(100.0, len(scores) * 2.0))
        confidence = max(0.0, min(100.0, 0.45 * breadth + 0.35 * (100.0 - concentration) + 0.2 * min(100.0, n)))
        degraded = "LOW_CONFIDENCE" if confidence < 35 else None

        metrics = {
            "active_wallet_count": len(scores),
            "avg_score": sum(float(x["score_total"]) for x in scores) / len(scores),
            "benchmark_equity_index_approx": 1000.0 + sum(float(x["score_total"]) for x in scores) / len(scores),
        }

        db.execute(
            text(
                """
                INSERT INTO wallet_cohort_snapshot(cohort_id, cohort_version, as_of_ts, metrics_json, signal_state, confidence_score)
                VALUES (:cohort_id, :cohort_version, :as_of_ts, CAST(:metrics_json AS jsonb), :signal_state, :confidence_score)
                """
            ),
            {
                "cohort_id": cohort_id,
                "cohort_version": cohort_version,
                "as_of_ts": now_ms,
                "metrics_json": json.dumps(metrics),
                "signal_state": bias_state,
                "confidence_score": confidence,
            },
        )

        db.execute(
            text(
                """
                INSERT INTO wallet_benchmark_signal(
                  cohort_id, signal_ts, bias_state, bias_strength, breadth_score, concentration_score,
                  active_wallet_count, benchmark_confidence, outputs_json, model_version, degraded_state
                ) VALUES (
                  :cohort_id, :signal_ts, :bias_state, :bias_strength, :breadth, :concentration,
                  :active_wallet_count, :confidence, CAST(:outputs_json AS jsonb), :model_version, :degraded_state
                )
                """
            ),
            {
                "cohort_id": cohort_id,
                "signal_ts": now_ms,
                "bias_state": bias_state,
                "bias_strength": bias_strength,
                "breadth": breadth,
                "concentration": concentration,
                "active_wallet_count": len(scores),
                "confidence": confidence,
                "outputs_json": json.dumps(metrics),
                "model_version": SIGNAL_VERSION,
                "degraded_state": degraded,
            },
        )
        db.commit()

        return {
            "cohort_id": cohort_id,
            "cohort_version": cohort_version,
            "members": len(scores),
            "signal": bias_state,
            "confidence": confidence,
        }

    def get_wallet_explainability(self, db: Session, wallet_id: str, *, event_limit: int = 25):
        wallet = db.execute(
            text("SELECT id, chain, address, manual_force_include, manual_force_exclude FROM wallet_master WHERE id=:wallet_id"),
            {"wallet_id": wallet_id},
        ).mappings().first()
        if not wallet:
            return None

        classification = db.execute(
            text(
                """
                SELECT class_label, confidence_score, excluded, reason_codes, rule_version, effective_from
                FROM wallet_classification
                WHERE wallet_id=:wallet_id
                ORDER BY effective_from DESC
                LIMIT 1
                """
            ),
            {"wallet_id": wallet_id},
        ).mappings().first()

        eligibility = db.execute(
            text(
                """
                SELECT lookback_days, eligible, failed_rules, metrics_json, threshold_version, generated_at
                FROM wallet_eligibility_snapshot
                WHERE wallet_id=:wallet_id
                ORDER BY generated_at DESC
                LIMIT 1
                """
            ),
            {"wallet_id": wallet_id},
        ).mappings().first()

        scores = db.execute(
            text(
                """
                SELECT window_days, score_total, component_scores, penalties_json, score_version, generated_at
                FROM wallet_score_snapshot
                WHERE wallet_id=:wallet_id
                ORDER BY generated_at DESC
                LIMIT 10
                """
            ),
            {"wallet_id": wallet_id},
        ).mappings().all()

        inferred = db.execute(
            text(
                """
                SELECT id, side, confidence_tier, confidence_score, notional_usd_est, event_ts, inference_version, reason_codes
                FROM wallet_inferred_event
                WHERE wallet_id=:wallet_id
                ORDER BY event_ts DESC
                LIMIT :event_limit
                """
            ),
            {"wallet_id": wallet_id, "event_limit": event_limit},
        ).mappings().all()

        return {
            "wallet": dict(wallet),
            "classification": dict(classification) if classification else None,
            "eligibility": dict(eligibility) if eligibility else None,
            "scores": [dict(x) for x in scores],
            "recent_inferred_events": [dict(x) for x in inferred],
        }

    def tag_alignment(self, db: Session, *, strategy_side: str, scope: str, strategy_instance_id: str | None = None, trade_ref: str | None = None):
        row = db.execute(
            text(
                """
                SELECT id, bias_state, bias_strength, benchmark_confidence, degraded_state, signal_ts
                FROM wallet_benchmark_signal
                ORDER BY signal_ts DESC
                LIMIT 1
                """
            )
        ).mappings().first()

        if not row:
            state = "insufficient_benchmark_confidence"
            signal_id = None
            details = {"reason": "no_signal"}
        else:
            signal_id = row["id"]
            conf = float(row["benchmark_confidence"] or 0.0)
            degraded = row["degraded_state"]
            bias = row["bias_state"]
            s = (strategy_side or "").lower()
            is_buy = s in {"buy", "long", "bullish"}
            is_sell = s in {"sell", "short", "bearish"}

            if conf < settings.wallet_intel_alignment_min_confidence or degraded == "LOW_CONFIDENCE":
                state = "insufficient_benchmark_confidence"
            elif bias == "neutral" or (not is_buy and not is_sell):
                state = "neutral"
            elif bias == "bullish":
                state = "aligned_bullish" if is_buy else "opposed_bullish"
            elif bias == "bearish":
                state = "aligned_bearish" if is_sell else "opposed_bearish"
            else:
                state = "neutral"

            details = {
                "signal_ts": row["signal_ts"],
                "bias_state": bias,
                "bias_strength": row["bias_strength"],
                "benchmark_confidence": conf,
                "degraded_state": degraded,
                "min_confidence_required": settings.wallet_intel_alignment_min_confidence,
            }

        db.execute(
            text(
                """
                INSERT INTO strategy_benchmark_alignment(strategy_instance_id, trade_ref, scope, alignment_state, benchmark_signal_id, details_json, ts)
                VALUES (:strategy_instance_id, :trade_ref, :scope, :alignment_state, :benchmark_signal_id, CAST(:details_json AS jsonb), :ts)
                """
            ),
            {
                "strategy_instance_id": strategy_instance_id,
                "trade_ref": trade_ref,
                "scope": scope,
                "alignment_state": state,
                "benchmark_signal_id": signal_id,
                "details_json": json.dumps(details),
                "ts": int(time.time() * 1000),
            },
        )
        db.commit()
        return {"alignment_state": state, "benchmark_signal_id": signal_id, "details": details}

    def run_pipeline(self, db: Session, *, provider_events: list[dict] | None = None):
        run_id = f"wrun_{uuid.uuid4().hex[:10]}"
        now_ms = int(time.time() * 1000)
        provider_events = provider_events or []

        for e in provider_events:
            wallet_id = self.ensure_wallet(db, chain=e.get("chain", "solana"), address=e["wallet_address"])
            raw_id = self.ingest_raw_event(
                db,
                wallet_id=wallet_id,
                provider=e.get("provider", "manual"),
                provider_event_id=e.get("provider_event_id", f"evt_{uuid.uuid4().hex[:8]}"),
                chain=e.get("chain", "solana"),
                event_ts=int(e.get("event_ts", now_ms)),
                payload=e.get("payload", {}),
            )
            can_id = self.normalize_event(db, wallet_id=wallet_id, raw_id=raw_id, event_ts=int(e.get("event_ts", now_ms)), payload=e.get("payload", {}))
            self.infer_event(db, wallet_id=wallet_id, canonical_id=can_id, event_ts=int(e.get("event_ts", now_ms)), payload=e.get("payload", {}))

        self.classify_wallets(db, run_id=run_id, now_ms=now_ms)
        self.compute_eligibility(db, run_id=run_id, now_ms=now_ms)
        self.compute_scores(db, run_id=run_id, now_ms=now_ms)
        signal = self.build_cohort_and_signal(db, run_id=run_id, now_ms=now_ms)
        return {"ok": True, "run_id": run_id, "signal": signal}
