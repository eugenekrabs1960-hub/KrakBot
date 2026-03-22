from __future__ import annotations

import json
import logging
import threading
import time
from datetime import datetime, timezone

import requests

from app.core.config import settings
from app.schemas.decision_output import DecisionOutput
from app.schemas.feature_packet import FeaturePacket
from app.services.models.adapter_base import LocalModelAdapter

logger = logging.getLogger(__name__)


class QwenLocalAdapter(LocalModelAdapter):
    _probe_ok: bool | None = None
    _probe_ts: float = 0.0
    _probe_ttl_sec: float = 10.0

    # instrumentation / safeguards
    _lock = threading.BoundedSemaphore(value=1)
    _active_requests = 0
    _active_lock = threading.Lock()
    _total_calls = 0
    _fallback_calls = 0
    _max_active_seen = 0

    @classmethod
    def metrics_snapshot(cls) -> dict:
        with cls._active_lock:
            return {
                'active_requests': cls._active_requests,
                'total_calls': cls._total_calls,
                'fallback_calls': cls._fallback_calls,
                'max_concurrent_config': settings.llm_max_concurrent_requests,
                'timeout_sec': settings.llm_request_timeout_sec,
                'max_active_seen': cls._max_active_seen,
            }

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
            "You are an intraday paper-trading analyst in a learning-and-profit mode. Use only packet fields. "
            "Return strict JSON only with keys compatible with DecisionOutput. "
            "In paper mode, controlled participation is valuable: do not lazily default to no_trade. "
            "Use no_trade only when evidence is truly weak/contradictory or execution quality is poor. "
            "When directional evidence is reasonably coherent and tradability is acceptable, prefer a clear long/short call. "
            "Avoid setup_type='unclear' unless evidence is genuinely conflicting. "
            "Favor actionable setups over excessive hesitation, while staying bounded and non-reckless. "
            "If edge is moderate and risk is bounded, participating with a paper trade is acceptable. "
            "For long/short decisions, make conviction explicit and provide clear invalidation. "
            "Include conviction-aware leverage preference guidance: lower for moderate edge, higher for strong edge only when "
            "directional evidence, setup quality, and market cleanliness are aligned. "
            "Do not rely on confidence alone for high leverage; require both conviction and market quality. "
            "Decision cadence context: the trading loop evaluates roughly every 5 minutes (not continuously). "
            "Prefer setups that remain actionable across this cadence window; avoid ultra-short scalp precision that is likely stale by the next cycle. "
            "Frame thesis, invalidation, and conviction for the 5-minute loop cadence and realistic fee drag. "
            "Do NOT force trades when data is degraded/broken, and do NOT ignore hard risk limits or safety controls."
        )
        user = {
            "task": "Evaluate one FeaturePacket and return JSON. "
                    "Decisions are made on an approximately 5-minute loop cadence, so optimize for setups that remain valid over that window. "
                    "If choosing no_trade, provide concrete non-tradability evidence from packet fields. "
                    "If choosing long/short, provide concise thesis, specific invalidation, supported setup_type, and "
                    "conviction-aware execution_preference consistent with bounded adaptive leverage intent.",
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


    def _safe_float(self, v, default: float = 0.5, lo: float = 0.0, hi: float = 1.0) -> float:
        try:
            x = float(v)
        except Exception:
            x = default
        return max(lo, min(hi, x))

    def _sanitize_reasons(self, reasons, packet: FeaturePacket) -> list[dict]:
        out = []
        if isinstance(reasons, list):
            for r in reasons:
                if not isinstance(r, dict):
                    continue
                label = str(r.get('label') or 'model_reason').strip()[:64] or 'model_reason'
                strength = self._safe_float(r.get('strength'), default=0.5, lo=0.0, hi=1.0)
                explanation = str(r.get('explanation') or 'model_evidence').strip()[:240] or 'model_evidence'
                out.append({'label': label, 'strength': strength, 'explanation': explanation})
                if len(out) >= 4:
                    break
        if len(out) < 2:
            out = [
                {"label": "momentum_alignment", "strength": min(1.0, abs(packet.features.returns.momentum_score)), "explanation": f"momentum_score={packet.features.returns.momentum_score:.2f}"},
                {"label": "execution_quality", "strength": packet.ml_scores.tradability_score, "explanation": f"tradability_score={packet.ml_scores.tradability_score:.2f}"},
            ]
        return out

    def _sanitize_risks(self, risks, packet: FeaturePacket) -> list[dict]:
        out = []
        if isinstance(risks, list):
            for r in risks:
                if not isinstance(r, dict):
                    continue
                label = str(r.get('label') or 'model_risk').strip()[:64] or 'model_risk'
                severity = self._safe_float(r.get('severity'), default=0.5, lo=0.0, hi=1.0)
                explanation = str(r.get('explanation') or 'model_risk_signal').strip()[:240] or 'model_risk_signal'
                out.append({'label': label, 'severity': severity, 'explanation': explanation})
                if len(out) >= 4:
                    break
        if len(out) < 1:
            out = [{
                "label": "regime_contradiction",
                "severity": min(1.0, packet.ml_scores.contradiction_score),
                "explanation": f"contradiction_score={packet.ml_scores.contradiction_score:.2f}",
            }]
        return out


    def _sanitize_string_list(self, xs, default: list[str]) -> list[str]:
        out: list[str] = []
        if isinstance(xs, list):
            for x in xs:
                v = str(x).strip() if x is not None else ''
                if not v:
                    continue
                out.append(v[:120])
                if len(out) >= 10:
                    break
        return out or list(default)

    def _sanitize_invalidation(self, invalidation, action: str):
        if action not in ('long', 'short'):
            return None
        if not isinstance(invalidation, dict):
            return {"type": "thesis_failure", "value": None, "reason": "model_thesis_invalidated"}
        itype = str(invalidation.get('type') or 'thesis_failure')
        if itype not in {"price_level", "regime_break", "volatility_break", "thesis_failure", "null"}:
            itype = 'thesis_failure'
        val = invalidation.get('value')
        try:
            val = None if val is None else float(val)
        except Exception:
            val = None
        reason = invalidation.get('reason')
        reason = None if reason is None else str(reason)[:160]
        return {"type": itype, "value": val, "reason": reason}

    def _normalize_with_boundary_repair(self, packet: FeaturePacket, raw: dict, err: Exception) -> DecisionOutput:
        # boundary repair path: keep model intent when possible, force contract-safe shape
        action = str(raw.get("action") or "no_trade")
        if action not in ("long", "short", "no_trade"):
            action = "no_trade"
        conf = self._safe_float(raw.get("confidence", 0.45), default=0.45, lo=0.0, hi=1.0)
        setup = str(raw.get("setup_type") or ("mean_reversion" if action in ("long", "short") else "unclear"))
        if setup not in ("trend_continuation", "breakout_confirmation", "mean_reversion", "range_rejection", "unclear"):
            setup = "mean_reversion" if action in ("long", "short") else "unclear"
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
            "horizon": packet.decision_context.primary_horizon if packet.decision_context.primary_horizon in ("15m","1h","4h") else "1h",
            "confidence": conf,
            "uncertainty": max(0.0, min(1.0, 1.0-conf)),
            "thesis_summary": str(raw.get("thesis_summary") or raw.get("reasoning") or f"model_output_boundary_repaired:{type(err).__name__}")[:500],
            "reasons": self._sanitize_reasons(raw.get("reasons"), packet),
            "risks": self._sanitize_risks(raw.get("risks"), packet),
            "invalidation": self._sanitize_invalidation(raw.get("invalidation"), action),
            "targets": {
                "take_profit_hint": None,
                "expected_move_magnitude": "small" if action != "no_trade" else "null",
            },
            "evidence_used": self._sanitize_string_list(raw.get("evidence_used"), ["features.returns.momentum_score","ml_scores.trade_quality_prior"]),
            "evidence_ignored": self._sanitize_string_list(raw.get("evidence_ignored"), ["optional_signals.news_summary"]),
            "alternatives_considered": [{"action": "no_trade", "reason": "boundary_repair_default"}],
            "execution_preference": {"urgency": "normal" if action != "no_trade" else "low", "entry_style_hint": "market_or_aggressive_limit" if action != "no_trade" else "none"},
        }
        return DecisionOutput.model_validate(out)

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

        reasons = self._sanitize_reasons(raw.get("reasons"), packet)

        risks = self._sanitize_risks(raw.get("risks"), packet)

        invalidation = self._sanitize_invalidation(raw.get("invalidation"), action)

        targets = raw.get("targets") or {}
        if not isinstance(targets, dict):
            targets = {}
        tpm = targets.get('take_profit_hint')
        try:
            tpm = None if tpm is None else float(tpm)
        except Exception:
            tpm = None
        emm = str(targets.get('expected_move_magnitude') or ('small' if action != 'no_trade' else 'null'))
        if emm not in {'small','medium','large','null'}:
            emm = 'small' if action != 'no_trade' else 'null'
        targets = {'take_profit_hint': tpm, 'expected_move_magnitude': emm}

        evidence_used = self._sanitize_string_list(raw.get("evidence_used"), ["features.returns.momentum_score", "ml_scores.tradability_score"])

        alternatives = raw.get("alternatives_considered")
        alt_out = []
        if isinstance(alternatives, list):
            for a in alternatives:
                if not isinstance(a, dict):
                    continue
                aa = str(a.get('action') or 'no_trade')
                if aa not in {'long','short','no_trade'}:
                    aa = 'no_trade'
                rr = str(a.get('reason') or 'model_alternative').strip()[:160] or 'model_alternative'
                alt_out.append({'action': aa, 'reason': rr})
                if len(alt_out) >= 3:
                    break
        alternatives = alt_out or [{"action": "no_trade", "reason": "normalization_default"}]

        exec_pref = raw.get("execution_preference") or {}
        if not isinstance(exec_pref, dict):
            exec_pref = {}
        urg = str(exec_pref.get('urgency') or ('normal' if action != 'no_trade' else 'low'))
        if urg not in {'low','normal','high'}:
            urg = 'normal' if action != 'no_trade' else 'low'
        style = str(exec_pref.get('entry_style_hint') or ('market_or_aggressive_limit' if action != 'no_trade' else 'none'))
        if style not in {'market','limit','market_or_aggressive_limit','passive_limit','none'}:
            style = 'market_or_aggressive_limit' if action != 'no_trade' else 'none'
        exec_pref = {'urgency': urg, 'entry_style_hint': style}

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
            "evidence_ignored": self._sanitize_string_list(raw.get("evidence_ignored"), []),
            "alternatives_considered": alternatives,
            "execution_preference": exec_pref,
        }
        return DecisionOutput.model_validate(out)

    def _deterministic_fallback(self, packet: FeaturePacket) -> DecisionOutput:
        with self._active_lock:
            self.__class__._fallback_calls += 1
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
        with self._active_lock:
            self.__class__._total_calls += 1

        acquired = self._lock.acquire(timeout=0.5)
        if not acquired:
            logger.warning('llm_call_skipped_concurrency_guard packet=%s', packet.packet_id)
            return self._deterministic_fallback(packet)

        with self._active_lock:
            self.__class__._active_requests += 1
            self.__class__._max_active_seen = max(self.__class__._max_active_seen, self.__class__._active_requests)

        started = time.perf_counter()
        try:
            if not self._model_available():
                return self._deterministic_fallback(packet)

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

            payload_size = len(json.dumps(payload, separators=(",", ":")))
            logger.info('llm_call_start packet=%s active=%s payload_bytes=%s', packet.packet_id, self.metrics_snapshot()['active_requests'], payload_size)

            r = requests.post(
                f"{settings.local_model_base_url.rstrip('/')}/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=settings.llm_request_timeout_sec,
            )
            r.raise_for_status()
            body = r.json()
            text = body["choices"][0]["message"]["content"]
            parsed = self._extract_json(text)
            try:
                out = self._normalize(packet, parsed)
                return out
            except Exception as norm_err:
                logger.warning('llm_call_boundary_repair packet=%s err=%s', packet.packet_id, repr(norm_err))
                return self._normalize_with_boundary_repair(packet, parsed if isinstance(parsed, dict) else {}, norm_err)
        except Exception as e:
            logger.warning('llm_call_fail packet=%s err=%s', packet.packet_id, repr(e))
            return self._deterministic_fallback(packet)
        finally:
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            with self._active_lock:
                self.__class__._active_requests = max(0, self.__class__._active_requests - 1)
            self._lock.release()
            logger.info('llm_call_end packet=%s latency_ms=%s metrics=%s', packet.packet_id, elapsed_ms, self.metrics_snapshot())
