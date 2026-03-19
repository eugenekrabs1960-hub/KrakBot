from __future__ import annotations

import json
import time
from datetime import datetime, timezone

import requests

from app.core.config import settings
from app.schemas.decision_output import DecisionOutput
from app.schemas.feature_packet import FeaturePacket
from app.services.models.adapter_base import LocalModelAdapter


class QwenLocalAdapter(LocalModelAdapter):
    _probe_ok: bool | None = None
    _probe_ts: float = 0.0
    _probe_ttl_sec: float = 10.0

    def _model_available(self) -> bool:
        now = time.time()
        if self._probe_ok is not None and (now - self._probe_ts) < self._probe_ttl_sec:
            return self._probe_ok
        headers = {}
        if settings.local_model_api_key:
            headers['Authorization'] = f"Bearer {settings.local_model_api_key}"
        try:
            r = requests.get(f"{settings.local_model_base_url.rstrip('/')}/v1/models", headers=headers, timeout=1.2)
            self._probe_ok = r.status_code == 200
        except Exception:
            self._probe_ok = False
        self._probe_ts = now
        return bool(self._probe_ok)

    def _build_messages(self, packet: FeaturePacket) -> list[dict]:
        system = (
            "You are a disciplined local trading analyst. Use only packet fields. "
            "Return strict JSON only with keys compatible with DecisionOutput."
        )
        user = {
            "task": "Evaluate one FeaturePacket and return JSON.",
            "packet": packet.model_dump(mode="json"),
        }
        return [
            {"role": "system", "content": system},
            {"role": "user", "content": json.dumps(user)},
        ]

    def _extract_json(self, text: str) -> dict:
        text = text.strip()
        if text.startswith("```"):
            text = text.strip("`")
            if text.lower().startswith("json"):
                text = text[4:].strip()
        try:
            return json.loads(text)
        except Exception:
            pass
        l = text.find("{")
        r = text.rfind("}")
        if l >= 0 and r > l:
            return json.loads(text[l : r + 1])
        raise ValueError("no_json_object_found")

    def _normalize(self, packet: FeaturePacket, raw: dict) -> DecisionOutput:
        action = raw.get("action")
        if action not in ("long", "short", "no_trade"):
            action = "no_trade"

        conf = float(raw.get("confidence", 0.45))
        conf = max(0.0, min(1.0, conf))
        uncertainty = float(raw.get("uncertainty", 1.0 - conf))
        uncertainty = max(0.0, min(1.0, uncertainty))

        setup = raw.get("setup_type", "unclear")
        if setup not in ("trend_continuation", "breakout_confirmation", "mean_reversion", "range_rejection", "unclear"):
            setup = "unclear"

        horizon = raw.get("horizon", packet.decision_context.primary_horizon)
        if horizon not in ("15m", "1h", "4h"):
            horizon = "1h"

        thesis = raw.get("thesis_summary") or raw.get("reasoning") or "model_output_normalized"

        reasons = raw.get("reasons")
        if not isinstance(reasons, list) or len(reasons) < 2:
            reasons = [
                {"label": "momentum_alignment", "strength": min(1.0, abs(packet.features.returns.momentum_score)), "explanation": f"momentum_score={packet.features.returns.momentum_score:.2f}"},
                {"label": "execution_quality", "strength": packet.ml_scores.tradability_score, "explanation": f"tradability_score={packet.ml_scores.tradability_score:.2f}"},
            ]

        risks = raw.get("risks")
        if not isinstance(risks, list) or len(risks) < 1:
            risks = [
                {
                    "label": "regime_contradiction",
                    "severity": min(1.0, packet.ml_scores.contradiction_score),
                    "explanation": f"contradiction_score={packet.ml_scores.contradiction_score:.2f}",
                }
            ]

        invalidation = raw.get("invalidation")
        if action in ("long", "short") and not invalidation:
            invalidation = {"type": "thesis_failure", "value": None, "reason": "model_thesis_invalidated"}

        targets = raw.get("targets") or {"take_profit_hint": None, "expected_move_magnitude": "small" if action != "no_trade" else "null"}

        evidence_used = raw.get("evidence_used")
        if not isinstance(evidence_used, list) or not evidence_used:
            evidence_used = ["features.returns.momentum_score", "ml_scores.tradability_score"]

        alternatives = raw.get("alternatives_considered")
        if not isinstance(alternatives, list) or not alternatives:
            alternatives = [{"action": "no_trade", "reason": "normalization_default"}]

        exec_pref = raw.get("execution_preference") or {"urgency": "normal" if action != "no_trade" else "low", "entry_style_hint": "market_or_aggressive_limit" if action != "no_trade" else "none"}

        out = {
            "decision_version": "1.0",
            "packet_id": packet.packet_id,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "model_name": settings.local_model_name,
            "model_role": "local_analyst",
            "coin": packet.coin,
            "symbol": packet.symbol,
            "action": action,
            "setup_type": setup,
            "horizon": horizon,
            "confidence": conf,
            "uncertainty": uncertainty,
            "thesis_summary": thesis,
            "reasons": reasons,
            "risks": risks,
            "invalidation": invalidation,
            "targets": targets,
            "evidence_used": evidence_used,
            "evidence_ignored": raw.get("evidence_ignored", []),
            "alternatives_considered": alternatives,
            "execution_preference": exec_pref,
        }
        return DecisionOutput.model_validate(out)

    def _deterministic_fallback(self, packet: FeaturePacket) -> DecisionOutput:
        m = packet.features.returns.momentum_score
        t = packet.ml_scores.tradability_score
        action = "long" if m > 0.2 else ("short" if m < -0.2 else "no_trade")
        setup = "mean_reversion" if action != "no_trade" else "unclear"
        conf = min(0.69, max(0.32, 0.45 + 0.25 * abs(m) + 0.15 * t)) if action != "no_trade" else 0.33
        uncertainty = min(0.95, max(0.05, 1.0 - conf))
        inv = None if action == "no_trade" else {"type": "thesis_failure", "value": None, "reason": "momentum weakens"}
        return DecisionOutput(
            packet_id=packet.packet_id,
            generated_at=datetime.now(timezone.utc),
            model_name=settings.local_model_name,
            coin=packet.coin,
            symbol=packet.symbol,
            action=action,
            setup_type=setup,
            horizon=packet.decision_context.primary_horizon,
            confidence=conf,
            uncertainty=uncertainty,
            thesis_summary="fallback_local_analyst_decision",
            reasons=[
                {"label": "momentum_alignment", "strength": min(1.0, abs(m)), "explanation": f"momentum_score={m:.2f}"},
                {"label": "execution_quality", "strength": t, "explanation": f"tradability_score={t:.2f}"},
            ],
            risks=[{"label": "regime_shift", "severity": min(1.0, packet.ml_scores.contradiction_score), "explanation": "contradiction risk"}],
            invalidation=inv,
            targets={"take_profit_hint": None, "expected_move_magnitude": "small" if action != "no_trade" else "null"},
            evidence_used=["features.returns.momentum_score", "ml_scores.tradability_score"],
            evidence_ignored=["optional_signals.news_summary", "optional_signals.social_summary"],
            alternatives_considered=[{"action": "no_trade", "reason": "if edge weakens"}],
            execution_preference={"urgency": "normal" if action != "no_trade" else "low", "entry_style_hint": "market_or_aggressive_limit" if action != "no_trade" else "none"},
        )

    def analyze(self, packet: FeaturePacket) -> DecisionOutput:
        if not self._model_available():
            return self._deterministic_fallback(packet)
        try:
            messages = self._build_messages(packet)
            headers = {"content-type": "application/json"}
            if settings.local_model_api_key:
                headers["authorization"] = f"Bearer {settings.local_model_api_key}"
            payload = {
                "model": settings.local_model_name,
                "messages": messages,
                "temperature": settings.local_model_temperature,
                "max_tokens": settings.local_model_max_tokens,
            }
            r = requests.post(
                f"{settings.local_model_base_url.rstrip('/')}/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=settings.local_model_timeout_sec,
            )
            r.raise_for_status()
            body = r.json()
            text = body["choices"][0]["message"]["content"]
            parsed = self._extract_json(text)
            return self._normalize(packet, parsed)
        except Exception:
            return self._deterministic_fallback(packet)
