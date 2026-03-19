from __future__ import annotations

import json
from datetime import datetime, timezone

import requests

from app.core.config import settings
from app.schemas.decision_output import DecisionOutput
from app.schemas.feature_packet import FeaturePacket
from app.services.models.adapter_base import LocalModelAdapter


class QwenLocalAdapter(LocalModelAdapter):
    def _build_messages(self, packet: FeaturePacket) -> list[dict]:
        system = (
            "You are a disciplined local trading analyst. Use only packet fields. "
            "Return strict JSON only matching DecisionOutput v1 fields. "
            "Be conservative; prefer no_trade for weak/conflicting setups."
        )
        user = {
            "task": "Evaluate one FeaturePacket and return DecisionOutput JSON only.",
            "constraints": {
                "action": ["long", "short", "no_trade"],
                "setup_type": ["trend_continuation", "breakout_confirmation", "mean_reversion", "range_rejection", "unclear"],
                "horizon": ["15m", "1h", "4h"],
                "rules": [
                    "at least 2 reasons",
                    "at least 1 risk",
                    "confidence and uncertainty in [0,1]",
                    "if action is long/short, invalidation required",
                ],
            },
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
        # try direct parse first
        try:
            return json.loads(text)
        except Exception:
            pass
        # fallback: first {...} block
        l = text.find("{")
        r = text.rfind("}")
        if l >= 0 and r > l:
            return json.loads(text[l : r + 1])
        raise ValueError("no_json_object_found")

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
            parsed.setdefault("packet_id", packet.packet_id)
            parsed.setdefault("generated_at", datetime.now(timezone.utc).isoformat())
            parsed.setdefault("model_name", settings.local_model_name)
            parsed.setdefault("coin", packet.coin)
            parsed.setdefault("symbol", packet.symbol)
            parsed.setdefault("model_role", "local_analyst")
            return DecisionOutput.model_validate(parsed)
        except Exception:
            return self._deterministic_fallback(packet)
