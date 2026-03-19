from datetime import datetime, timezone
import re
from pathlib import Path
from typing import Any
import json
import asyncio

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from hyperliquid_paper import HyperliquidFuturesPaperTrack

app = FastAPI(title="BTC Paper Backend")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

PAIR = "XBTUSD"
TRIGGER_UPPER = 69513.0
TRIGGER_LOWER = 68698.6

# Kraken Pro spot fee model (configurable base tier, paper-only assumptions)
PAPER_FEE_MODEL = "kraken_pro_spot_tiered"
KRAKEN_PRO_SPOT_FEE_TIERS = [
    {"volume_usd": 500_000, "maker_pct": 0.08, "taker_pct": 0.18},
    {"volume_usd": 250_000, "maker_pct": 0.10, "taker_pct": 0.20},
    {"volume_usd": 100_000, "maker_pct": 0.12, "taker_pct": 0.22},
    {"volume_usd": 50_000, "maker_pct": 0.14, "taker_pct": 0.24},
    {"volume_usd": 10_000, "maker_pct": 0.20, "taker_pct": 0.35},
    {"volume_usd": 0, "maker_pct": 0.25, "taker_pct": 0.40},
]
# Small, controlled first step: fixed configurable tier (no rolling 30d tracking yet).
KRAKEN_PRO_BASE_30D_VOLUME_USD = 0.0
# Execution assumptions for paper fills; default remains conservative taker-only.
KRAKEN_ENTRY_LIQUIDITY_ASSUMPTION = "taker"
KRAKEN_EXIT_LIQUIDITY_ASSUMPTION = "taker"

# 15m experiment controls (different family from frozen baseline)
EXPERIMENT_MAX_SPREAD_PCT = 0.08
EXPERIMENT_MIN_RISK_PCT = 0.18
EXPERIMENT_MAX_RISK_PCT = 1.20
BRK_RETEST_LOOKBACK = 8
MAX_OPEN_POSITIONS_PER_MODE = 2
CONSERVATIVE_MIN_REWARD_TO_FEE = 1.50
CONSERVATIVE_NETEDGE_V1_MIN_REWARD_TO_FEE = 2.20
# Safety/conservation mode: Kraken scan path can run without LLM calls.
KRAKEN_USE_LLM_SCAN = False

MODE_CONFIGS = {
    "btc_15m_conservative": {
        "label": "BTC/USD 15m conservative (frozen baseline)",
        "interval": 15,
        "rr_min": 1.5,
        "aggressive": False,
        "fee_bps_entry": 40.0,
        "fee_bps_exit": 40.0,
        "enable_time_exit": False,
        "max_bars_open": 0,
        "max_minutes_open": 0,
        "enable_invalidation_exit": False,
    },
    "btc_15m_conservative_netedge_v1": {
        "label": "BTC/USD 15m conservative netedge v1 (experimental)",
        "interval": 15,
        "rr_min": 1.5,
        "aggressive": False,
        "fee_bps_entry": 40.0,
        "fee_bps_exit": 40.0,
        "enable_time_exit": False,
        "max_bars_open": 0,
        "max_minutes_open": 0,
        "enable_invalidation_exit": False,
    },
    "btc_15m_conservative_inverse_v1": {
        "label": "BTC/USD 15m conservative inverse v1 (experimental)",
        "interval": 15,
        "rr_min": 1.5,
        "aggressive": False,
        "fee_bps_entry": 40.0,
        "fee_bps_exit": 40.0,
        "enable_time_exit": False,
        "max_bars_open": 0,
        "max_minutes_open": 0,
        "enable_invalidation_exit": False,
    },
    "btc_15m_breakout_retest": {
        "label": "BTC/USD 15m breakout-retest experiment",
        "interval": 15,
        "rr_min": 1.35,
        "aggressive": True,
        "fee_bps_entry": 40.0,
        "fee_bps_exit": 40.0,
        "enable_time_exit": False,
        "max_bars_open": 0,
        "max_minutes_open": 0,
        "enable_invalidation_exit": False,
    },
}

STRATEGY_REGISTRY = {
    "btc_15m_conservative": {
        "strategy_key": "btc_15m_conservative",
        "label": "BTC/USD 15m conservative (frozen baseline)",
        "family": "trend_structure",
        "timeframe": "15m",
        "status": "frozen",
        "paper_only": True,
        "routing_enabled": False,
        "allowed_regimes": ["trend", "breakout", "chop"],
        "notes": "Frozen baseline. Execution behavior must remain unchanged during Phase 1 architecture work.",
    },
    "btc_15m_conservative_netedge_v1": {
        "strategy_key": "btc_15m_conservative_netedge_v1",
        "label": "BTC/USD 15m conservative netedge v1 (experimental)",
        "family": "trend_structure",
        "timeframe": "15m",
        "status": "experimental",
        "paper_only": True,
        "routing_enabled": False,
        "allowed_regimes": ["trend", "breakout", "chop"],
        "notes": "Controlled conservative experiment: only the after-fee net-edge gate is tightened versus frozen baseline.",
    },
    "btc_15m_conservative_inverse_v1": {
        "strategy_key": "btc_15m_conservative_inverse_v1",
        "label": "BTC/USD 15m conservative inverse v1 (experimental)",
        "family": "trend_structure_inverse",
        "timeframe": "15m",
        "status": "experimental",
        "paper_only": True,
        "routing_enabled": False,
        "allowed_regimes": ["trend", "breakout", "chop"],
        "notes": "Directional hypothesis test: mechanically invert conservative direction while preserving paper controls.",
    },
    "btc_15m_breakout_retest": {
        "strategy_key": "btc_15m_breakout_retest",
        "label": "BTC/USD 15m breakout-retest experiment",
        "family": "breakout_retest",
        "timeframe": "15m",
        "status": "experimental",
        "paper_only": True,
        "routing_enabled": False,
        "allowed_regimes": ["breakout", "trend", "low_edge"],
        "notes": "Approved strategy family in paper mode only. No autonomous routing in Phase 1.",
    },
}

REGIME_TYPES = ["trend", "chop", "breakout", "low_edge"]

BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent
STATE_DIR = BASE_DIR / "data"
STATE_FILE = STATE_DIR / "paper_state.json"
FRONTEND_DIST_DIR = PROJECT_DIR / "frontend" / "dist"


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def round2(x: float) -> float:
    return round(float(x), 2)


def safe_div(a: float, b: float) -> float:
    return round2(a / b) if b else 0.0


def fee_from_notional(notional: float, fee_bps: float) -> float:
    return round2(float(notional) * (float(fee_bps) / 10000.0))


def paper_entry_fee(mode_cfg: dict[str, Any], entry_notional: float) -> dict[str, Any]:
    fee_bps = float(mode_cfg.get("fee_bps_entry", 40.0))
    return {
        "fee": fee_from_notional(entry_notional, fee_bps),
        "fee_bps": fee_bps,
        "fee_pct": round2(fee_bps / 100.0),
        "liquidity": "taker",
    }


def paper_exit_fee(mode_cfg: dict[str, Any], exit_notional: float) -> dict[str, Any]:
    fee_bps = float(mode_cfg.get("fee_bps_exit", mode_cfg.get("fee_bps_entry", 40.0)))
    return {
        "fee": fee_from_notional(exit_notional, fee_bps),
        "fee_bps": fee_bps,
        "fee_pct": round2(fee_bps / 100.0),
        "liquidity": "taker",
    }


def kraken_pro_spot_fee_tier(volume_usd: float | None = None) -> dict[str, float]:
    v = KRAKEN_PRO_BASE_30D_VOLUME_USD if volume_usd is None else float(volume_usd)
    for tier in KRAKEN_PRO_SPOT_FEE_TIERS:
        if v >= tier["volume_usd"]:
            return tier
    return KRAKEN_PRO_SPOT_FEE_TIERS[-1]


def kraken_fee_pct(liquidity: str = "taker", volume_usd: float | None = None) -> float:
    tier = kraken_pro_spot_fee_tier(volume_usd)
    return float(tier["maker_pct"] if str(liquidity).lower() == "maker" else tier["taker_pct"])


def kraken_fill_fee(notional: float, liquidity: str = "taker", volume_usd: float | None = None) -> dict[str, Any]:
    fee_pct = kraken_fee_pct(liquidity=liquidity, volume_usd=volume_usd)
    fee = float(notional) * (fee_pct / 100.0)
    return {
        "fee": round2(fee),
        "fee_pct": fee_pct,
        "liquidity": "maker" if str(liquidity).lower() == "maker" else "taker",
        "tier_30d_volume_usd": float(KRAKEN_PRO_BASE_30D_VOLUME_USD if volume_usd is None else volume_usd),
    }


def strategy_metrics_bucket() -> dict[str, Any]:
    return {
        "total_trades": 0,
        "open_trades": 0,
        "closed_trades": 0,
        "win_rate": 0.0,
        "average_win": 0.0,
        "average_loss": 0.0,
        "expectancy": 0.0,
        "realized_pnl": 0.0,
        "unrealized_pnl": 0.0,
        "total_fees": 0.0,
        "fee_drag_pct": 0.0,
        "max_drawdown": 0.0,
        "gross_realized_pnl": 0.0,
        "gross_unrealized_pnl": 0.0,
        "sample_size": 0,
    }


def regime_metrics_bucket() -> dict[str, Any]:
    return {regime: strategy_metrics_bucket() for regime in REGIME_TYPES}


def classify_market_regime(candles, bid, ask, spread_pct) -> dict[str, Any]:
    closes = [c["close"] for c in candles[-6:]]
    highs = [c["high"] for c in candles[-6:]]
    lows = [c["low"] for c in candles[-6:]]
    last = candles[-1]
    prev = candles[-2]
    lookback_ranges = [(c["high"] - c["low"]) for c in candles[-8:]]
    avg_range = max(sum(lookback_ranges) / len(lookback_ranges), 0.1)
    net_move = closes[-1] - closes[0]
    directionality = abs(net_move) / max(sum(abs(closes[i] - closes[i - 1]) for i in range(1, len(closes))), 0.1)
    six_bar_range = max(highs) - min(lows)
    breakout_up = last["close"] > max(highs[:-1])
    breakout_down = last["close"] < min(lows[:-1])
    breakout = breakout_up or breakout_down
    compression = safe_div(six_bar_range, max(last["close"], 1))
    spread_ok = spread_pct <= max(EXPERIMENT_MAX_SPREAD_PCT, 0.10)

    regime = "low_edge"
    confidence = 0.5
    subtype = "indecisive"
    reasons = []

    if not spread_ok:
        regime = "low_edge"
        confidence = 0.88
        subtype = "spread_dislocation"
        reasons.append("Spread is too wide for clean execution quality.")
    elif breakout and (last["high"] - last["low"]) >= 1.05 * avg_range:
        regime = "breakout"
        confidence = min(0.95, round2(0.62 + directionality * 0.25))
        subtype = "bullish_breakout" if breakout_up else "bearish_breakout"
        reasons.append("Recent candle expanded beyond short-term structure.")
    elif directionality >= 0.62 and compression >= 0.004:
        regime = "trend"
        confidence = min(0.9, round2(0.55 + directionality * 0.3))
        subtype = "uptrend" if net_move > 0 else "downtrend"
        reasons.append("Directional follow-through is stronger than short-term chop.")
    elif compression <= 0.0045 and abs(last["close"] - prev["close"]) <= 0.65 * avg_range:
        regime = "chop"
        confidence = 0.66
        subtype = "range_bound"
        reasons.append("Price is rotating in a relatively compressed range.")
    else:
        regime = "low_edge"
        confidence = 0.58
        subtype = "mixed_structure"
        reasons.append("No strong directional or breakout edge detected.")

    return {
        "regime": regime,
        "confidence": confidence,
        "subtype": subtype,
        "edge_ok": regime != "low_edge",
        "inputs": {
            "spread_pct": round2(spread_pct),
            "avg_range": round2(avg_range),
            "six_bar_range": round2(six_bar_range),
            "directionality": round2(directionality),
            "compression_pct": round2(compression * 100),
            "net_move": round2(net_move),
            "bid": round2(bid),
            "ask": round2(ask),
        },
        "reason": " ".join(reasons),
    }


def mode_bucket() -> dict[str, Any]:
    return {
        "latest": None,
        "last_candle_time": None,
        "notify_user": None,
        "history": [],
        "pending_orders": [],
        "open_positions": [],
        "closed_trades": [],
        "paper_execution_log": [],
        "executed_signal_ids": set(),
        "strategy_registry_entry": None,
        "current_regime": None,
        "strategy_metrics": strategy_metrics_bucket(),
        "performance_by_regime": regime_metrics_bucket(),
    }


store: dict[str, Any] = {
    "auto_scan": True,
    "modes": {k: mode_bucket() for k in MODE_CONFIGS.keys()},
}

# Separate futures-oriented paper training track (Phase 2/3). Non-destructive: Kraken path stays intact.
hyper_track = HyperliquidFuturesPaperTrack()


def _json_safe_store_snapshot() -> dict[str, Any]:
    modes: dict[str, Any] = {}
    for mode, bucket in store["modes"].items():
        modes[mode] = {
            "latest": bucket.get("latest"),
            "last_candle_time": bucket.get("last_candle_time"),
            "notify_user": bucket.get("notify_user"),
            "history": bucket.get("history", [])[-1000:],
            "pending_orders": bucket.get("pending_orders", []),
            "open_positions": bucket.get("open_positions", []),
            "closed_trades": bucket.get("closed_trades", [])[-500:],
            "paper_execution_log": bucket.get("paper_execution_log", [])[-500:],
            "executed_signal_ids": sorted(bucket.get("executed_signal_ids", set())),
            "strategy_registry_entry": bucket.get("strategy_registry_entry"),
            "current_regime": bucket.get("current_regime"),
            "strategy_metrics": bucket.get("strategy_metrics", strategy_metrics_bucket()),
            "performance_by_regime": bucket.get("performance_by_regime", regime_metrics_bucket()),
        }
    return {"auto_scan": store.get("auto_scan", True), "modes": modes}


def persist_store() -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    tmp = STATE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(_json_safe_store_snapshot(), separators=(",", ":")), encoding="utf-8")
    tmp.replace(STATE_FILE)


def load_store() -> None:
    if not STATE_FILE.exists():
        return
    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return
    store["auto_scan"] = bool(data.get("auto_scan", True))
    saved_modes = data.get("modes", {})
    for mode in MODE_CONFIGS.keys():
        bucket = mode_bucket()
        saved = saved_modes.get(mode, {}) if isinstance(saved_modes, dict) else {}
        bucket["latest"] = saved.get("latest")
        bucket["last_candle_time"] = saved.get("last_candle_time")
        bucket["notify_user"] = saved.get("notify_user")
        bucket["history"] = saved.get("history", [])[-1000:]
        bucket["pending_orders"] = saved.get("pending_orders", [])
        bucket["open_positions"] = saved.get("open_positions", [])
        bucket["closed_trades"] = saved.get("closed_trades", [])[-500:]
        bucket["paper_execution_log"] = saved.get("paper_execution_log", [])[-500:]
        bucket["executed_signal_ids"] = set(saved.get("executed_signal_ids", []))
        bucket["strategy_registry_entry"] = saved.get("strategy_registry_entry") or STRATEGY_REGISTRY.get(mode)
        bucket["current_regime"] = saved.get("current_regime")
        bucket["strategy_metrics"] = saved.get("strategy_metrics", strategy_metrics_bucket())
        bucket["performance_by_regime"] = saved.get("performance_by_regime", regime_metrics_bucket())
        if bucket["latest"]:
            bucket["latest"]["notify_user"] = bucket["notify_user"]
            bucket["latest"]["pending_orders"] = bucket["pending_orders"][-25:]
            bucket["latest"]["open_positions"] = bucket["open_positions"]
            bucket["latest"]["closed_trades"] = bucket["closed_trades"][-25:]
            bucket["latest"]["paper_execution_log"] = bucket["paper_execution_log"][-10:]
            bucket["latest"]["strategy_registry_entry"] = bucket["strategy_registry_entry"]
            bucket["latest"]["current_regime"] = bucket["current_regime"]
            bucket["latest"]["strategy_metrics"] = bucket["strategy_metrics"]
            bucket["latest"]["performance_by_regime"] = bucket["performance_by_regime"]
            bucket["latest"]["mode_stats"] = mode_stats(bucket, MODE_CONFIGS.get(mode, {}))
        store["modes"][mode] = bucket


async def fetch_market(interval: int):
    async with httpx.AsyncClient(timeout=20) as c:
        o = (await c.get(f"https://api.kraken.com/0/public/OHLC?pair={PAIR}&interval={interval}")).json()
        t = (await c.get(f"https://api.kraken.com/0/public/Ticker?pair={PAIR}")).json()
    k = next(x for x in o["result"].keys() if x != "last")
    rows = o["result"][k][-20:]
    candles = [{
        "time": datetime.fromtimestamp(int(r[0]), timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "open": float(r[1]), "high": float(r[2]), "low": float(r[3]), "close": float(r[4]), "volume": float(r[6])
    } for r in rows]
    tk = next(iter(t["result"].values()))
    bid, ask = float(tk["b"][0]), float(tk["a"][0])
    spread = ask - bid
    spread_pct = (spread / ((ask + bid) / 2)) * 100
    return candles, bid, ask, spread, spread_pct


def normalize_decision(d: dict[str, Any], rr_min: float):
    s = d.get("status", "INSUFFICIENT_DATA")
    if s not in {"PROPOSE_TRADE", "WAIT", "REJECT", "INSUFFICIENT_DATA"}:
        s = "INSUFFICIENT_DATA"
    n = {
        "status": s,
        "side": d.get("side", ""),
        "entry_price": d.get("entry_price", 0),
        "stop_loss": d.get("stop_loss", 0),
        "take_profit": d.get("take_profit", 0),
        "risk_reward_ratio": d.get("risk_reward_ratio", 0),
        "invalidation": d.get("invalidation", ""),
        "regime_label": d.get("regime_label", ""),
        "reason": d.get("reason", ""),
        "signal_id": d.get("signal_id", ""),
    }
    if n["status"] == "PROPOSE_TRADE":
        ok = all([
            n["side"] in {"BUY", "SELL"}, n["entry_price"] > 0, n["stop_loss"] > 0, n["take_profit"] > 0,
            n["risk_reward_ratio"] >= rr_min, n["invalidation"], n["regime_label"], n["reason"],
        ])
        if not ok:
            n.update({"status": "WAIT", "side": "", "entry_price": 0, "stop_loss": 0, "take_profit": 0, "risk_reward_ratio": 0, "invalidation": "", "reason": "Missing executable trade fields."})
    return n


def invert_conservative_decision(d: dict[str, Any], rr_min: float) -> dict[str, Any]:
    if d.get("status") != "PROPOSE_TRADE":
        return d
    side = d.get("side")
    entry = float(d.get("entry_price") or 0)
    stop = float(d.get("stop_loss") or 0)
    tp = float(d.get("take_profit") or 0)
    if side not in {"BUY", "SELL"} or entry <= 0 or stop <= 0 or tp <= 0:
        return normalize_decision({"status": "WAIT", "regime_label": "inverse_invalid_fields", "reason": "Inverse mode blocked: invalid baseline decision fields."}, rr_min)

    inv_side = "SELL" if side == "BUY" else "BUY"
    inv_stop = tp
    inv_tp = stop
    inv_rr = abs(entry - inv_tp) / max(abs(inv_stop - entry), 1e-9)

    if (inv_side == "BUY" and not (inv_stop < entry < inv_tp)) or (inv_side == "SELL" and not (inv_tp < entry < inv_stop)):
        return normalize_decision({"status": "WAIT", "regime_label": "inverse_invalid_structure", "reason": "Inverse mode blocked: inverted stop/take-profit structure is invalid."}, rr_min)

    return normalize_decision({
        **d,
        "side": inv_side,
        "stop_loss": round2(inv_stop),
        "take_profit": round2(inv_tp),
        "risk_reward_ratio": round2(inv_rr),
        "invalidation": f"inverse_of:{d.get('invalidation', '')}",
        "regime_label": f"inverse_{d.get('regime_label', 'unknown')}",
        "reason": f"Inverse v1 of conservative signal: {d.get('reason', '')}",
    }, rr_min)


def conservative_fee_efficiency_gate(d, mode: str):
    """Paper-only fee-adjusted efficiency gate for conservative family modes."""
    if d.get("status") != "PROPOSE_TRADE":
        return d

    threshold_by_mode = {
        "btc_15m_conservative": CONSERVATIVE_MIN_REWARD_TO_FEE,
        "btc_15m_conservative_netedge_v1": CONSERVATIVE_NETEDGE_V1_MIN_REWARD_TO_FEE,
        "btc_15m_conservative_inverse_v1": CONSERVATIVE_MIN_REWARD_TO_FEE,
    }
    min_reward_to_fee = float(threshold_by_mode.get(mode, CONSERVATIVE_MIN_REWARD_TO_FEE))
    rr_min = MODE_CONFIGS.get(mode, MODE_CONFIGS["btc_15m_conservative"])["rr_min"]

    side = d.get("side")
    entry = float(d.get("entry_price") or 0)
    tp = float(d.get("take_profit") or 0)
    qty = 1.0
    if side not in {"BUY", "SELL"} or entry <= 0 or tp <= 0:
        return normalize_decision({
            "status": "WAIT",
            "regime_label": "cons15_fee_efficiency_block",
            "reason": "Projected gross reward is too small relative to estimated round-trip fees.",
        }, rr_min)

    projected_entry_fee = kraken_fill_fee(entry * qty, KRAKEN_ENTRY_LIQUIDITY_ASSUMPTION)["fee"]
    projected_exit_fee = kraken_fill_fee(tp * qty, KRAKEN_EXIT_LIQUIDITY_ASSUMPTION)["fee"]
    projected_round_trip_fees = projected_entry_fee + projected_exit_fee
    projected_gross_reward = ((tp - entry) if side == "BUY" else (entry - tp)) * qty
    reward_to_fee_ratio = projected_gross_reward / projected_round_trip_fees if projected_round_trip_fees > 0 else 0.0

    if projected_gross_reward <= 0 or reward_to_fee_ratio < min_reward_to_fee:
        return normalize_decision({
            "status": "WAIT",
            "regime_label": "cons15_fee_efficiency_block",
            "reason": f"Projected gross reward is too small relative to estimated round-trip fees (min ratio {min_reward_to_fee:.2f}).",
        }, rr_min)

    d["projected_entry_fee"] = round2(projected_entry_fee)
    d["projected_exit_fee"] = round2(projected_exit_fee)
    d["projected_round_trip_fees"] = round2(projected_round_trip_fees)
    d["projected_gross_reward"] = round2(projected_gross_reward)
    d["reward_to_fee_ratio"] = round2(reward_to_fee_ratio)
    d["min_reward_to_fee_ratio_required"] = round2(min_reward_to_fee)
    return d


def aggressive_quality_gate(candles, d, bid, ask, spread_pct):
    """Extra safety/quality gates for 15m breakout-retest experiment only."""
    if d.get("status") != "PROPOSE_TRADE":
        return d

    side = d.get("side")
    entry = float(d.get("entry_price") or 0)
    stop = float(d.get("stop_loss") or 0)
    rr = float(d.get("risk_reward_ratio") or 0)
    if side not in {"BUY", "SELL"} or entry <= 0 or stop <= 0:
        return normalize_decision({"status": "WAIT", "regime_label": "brk15_filter_invalid_fields", "reason": "Breakout-retest gate blocked: invalid trade fields."}, 1.35)

    if spread_pct > EXPERIMENT_MAX_SPREAD_PCT:
        return normalize_decision({"status": "WAIT", "regime_label": "brk15_filter_spread", "reason": f"Breakout-retest gate blocked: spread too wide for 15m execution quality (>{EXPERIMENT_MAX_SPREAD_PCT}%)."}, 1.35)

    risk_pct = abs(entry - stop) / max(entry, 1) * 100
    if risk_pct < EXPERIMENT_MIN_RISK_PCT or risk_pct > EXPERIMENT_MAX_RISK_PCT:
        return normalize_decision({"status": "WAIT", "regime_label": "brk15_filter_risk_band", "reason": f"Breakout-retest gate blocked: stop distance outside {EXPERIMENT_MIN_RISK_PCT:.2f}%-{EXPERIMENT_MAX_RISK_PCT:.2f}% risk band."}, 1.35)
    if rr < 1.45:
        return normalize_decision({"status": "WAIT", "regime_label": "brk15_filter_rr", "reason": "Breakout-retest gate blocked: risk/reward below tightened 15m threshold (1.45)."}, 1.35)

    last, prev = candles[-1], candles[-2]
    if side == "BUY":
        if not (last["close"] >= prev["close"]):
            return normalize_decision({"status": "WAIT", "regime_label": "brk15_filter_confirmation", "reason": "Breakout-retest gate blocked: missing bullish 2-candle confirmation."}, 1.35)
        if ask > entry * 1.0018:
            return normalize_decision({"status": "WAIT", "regime_label": "brk15_filter_entry_chase", "reason": "Breakout-retest gate blocked: buy fill would chase too far above planned entry."}, 1.35)
    else:
        if not (last["close"] <= prev["close"]):
            return normalize_decision({"status": "WAIT", "regime_label": "brk15_filter_confirmation", "reason": "Breakout-retest gate blocked: missing bearish 2-candle confirmation."}, 1.35)
        if bid < entry * 0.9982:
            return normalize_decision({"status": "WAIT", "regime_label": "brk15_filter_entry_chase", "reason": "Breakout-retest gate blocked: sell fill would chase too far below planned entry."}, 1.35)

    return d


def fallback_construct(candles, rr_min, aggressive, timeframe):
    last, prev = candles[-1], candles[-2]
    highs5 = [c["high"] for c in candles[-5:]]
    lows5 = [c["low"] for c in candles[-5:]]
    highs6 = [c["high"] for c in candles[-6:]]
    lows6 = [c["low"] for c in candles[-6:]]
    ranges = [c["high"] - c["low"] for c in candles[-8:]]
    avg_range = max(0.1, sum(ranges) / len(ranges))

    # 15m experiment uses a different family: breakout-retest continuation.
    if aggressive:
        highsN = [c["high"] for c in candles[-BRK_RETEST_LOOKBACK:]]
        lowsN = [c["low"] for c in candles[-BRK_RETEST_LOOKBACK:]]
        breakout_high = max(highsN[:-1])
        breakout_low = min(lowsN[:-1])

        broke_up = last["close"] > breakout_high and prev["close"] <= breakout_high
        retest_up = last["low"] <= breakout_high * 1.0008
        confirm_up = last["close"] >= last["open"] and last["close"] >= breakout_high

        if broke_up and retest_up and confirm_up:
            e = round(last["high"] + 0.5, 1)
            st = round(min(lows5) - 0.5, 1)
            r = e - st
            tp = round(e + 1.8 * r, 1)
            rr = round((tp - e) / r, 2) if r > 0 else 0
            if rr >= rr_min:
                return normalize_decision({
                    "status": "PROPOSE_TRADE", "side": "BUY", "entry_price": e, "stop_loss": st, "take_profit": tp,
                    "risk_reward_ratio": rr, "invalidation": f"{timeframe} close back below {round(breakout_high,1)}",
                    "regime_label": "brk15_breakout_retest_long",
                    "reason": "15m experiment family: bullish breakout-retest continuation.",
                }, rr_min)

        broke_down = last["close"] < breakout_low and prev["close"] >= breakout_low
        retest_dn = last["high"] >= breakout_low * 0.9992
        confirm_dn = last["close"] <= last["open"] and last["close"] <= breakout_low

        if broke_down and retest_dn and confirm_dn:
            e = round(last["low"] - 0.5, 1)
            st = round(max(highs5) + 0.5, 1)
            r = st - e
            tp = round(e - 1.8 * r, 1)
            rr = round((e - tp) / r, 2) if r > 0 else 0
            if rr >= rr_min:
                return normalize_decision({
                    "status": "PROPOSE_TRADE", "side": "SELL", "entry_price": e, "stop_loss": st, "take_profit": tp,
                    "risk_reward_ratio": rr, "invalidation": f"{timeframe} close back above {round(breakout_low,1)}",
                    "regime_label": "brk15_breakout_retest_short",
                    "reason": "15m experiment family: bearish breakout-retest continuation.",
                }, rr_min)

        return normalize_decision({"status": "WAIT", "regime_label": "brk15_no_edge", "reason": "15m breakout-retest family found no qualified setup."}, rr_min)

    # Frozen baseline behavior for 15m conservative (strict confirmation)
    conf = 2

    # 1) bearish breakdown continuation
    if last["close"] < TRIGGER_LOWER and (conf == 1 or prev["close"] < TRIGGER_LOWER):
        e = round(min(last["low"], prev["low"]) - 1, 1)
        st = round(max(highs5) + 1, 1)
        r = st - e
        tp = round(e - 2.0 * r, 1)
        rr = round((e - tp) / r, 2) if r > 0 else 0
        if rr >= rr_min:
            return normalize_decision({
                "status": "PROPOSE_TRADE", "side": "SELL", "entry_price": e, "stop_loss": st, "take_profit": tp,
                "risk_reward_ratio": rr, "invalidation": f"{timeframe} close above {TRIGGER_LOWER}",
                "regime_label": "bearish_breakdown_continuation", "reason": "Bounded template: breakdown continuation.",
            }, rr_min)

    # 2) bullish reclaim recovery
    low_below = any(c["low"] < TRIGGER_LOWER for c in candles[-8:])
    if low_below and last["close"] > TRIGGER_LOWER and (conf == 1 or prev["close"] > TRIGGER_LOWER):
        e = round(max(highs5) + 1, 1)
        st = round(min(lows5) - 1, 1)
        r = e - st
        tp = round(e + 2.0 * r, 1)
        rr = round((tp - e) / r, 2) if r > 0 else 0
        if rr >= rr_min:
            return normalize_decision({
                "status": "PROPOSE_TRADE", "side": "BUY", "entry_price": e, "stop_loss": st, "take_profit": tp,
                "risk_reward_ratio": rr, "invalidation": f"{timeframe} close below {TRIGGER_LOWER}",
                "regime_label": "bullish_reclaim_recovery", "reason": "Bounded template: reclaim recovery.",
            }, rr_min)

    # 3) rebound into resistance (strictly conservative unless aggressive)
    if prev["high"] >= TRIGGER_UPPER * 0.997 and last["close"] < prev["close"]:
        e = round(last["low"] - 1.0, 1)
        st = round(max(highs5) + 1.0, 1)
        r = st - e
        tp = round(e - (1.8 * r), 1)
        rr = round((e - tp) / r, 2) if r > 0 else 0
        if rr >= rr_min:
            return normalize_decision({
                "status": "PROPOSE_TRADE", "side": "SELL", "entry_price": e, "stop_loss": st, "take_profit": tp,
                "risk_reward_ratio": rr, "invalidation": f"{timeframe} close above {TRIGGER_UPPER}",
                "regime_label": "rebound_into_resistance", "reason": "Bounded template: resistance rejection.",
            }, rr_min)

    # 4) consolidation breakout
    rng = max(highs6) - min(lows6)
    if last["close"] > max(highs6[:-1]) and rng / max(last["close"], 1) < 0.006:
        e = round(max(highs6) + 1.0, 1)
        st = round(min(lows6) - 1.0, 1)
        r = e - st
        tp = round(e + (1.8 * r), 1)
        rr = round((tp - e) / r, 2) if r > 0 else 0
        if rr >= rr_min:
            return normalize_decision({
                "status": "PROPOSE_TRADE", "side": "BUY", "entry_price": e, "stop_loss": st, "take_profit": tp,
                "risk_reward_ratio": rr, "invalidation": f"{timeframe} close below {round(min(lows6),1)}",
                "regime_label": "consolidation_breakout", "reason": "Bounded template: consolidation breakout.",
            }, rr_min)

    # Additional aggressive-only bounded templates (do NOT apply to frozen baseline)
    if aggressive:
        up_break = last["close"] > max(highs5[:-1]) and last["close"] > last["open"] and prev["close"] > prev["open"]
        dn_break = last["close"] < min(lows5[:-1]) and last["close"] < last["open"] and prev["close"] < prev["open"]
        strong_candle = (last["high"] - last["low"]) >= 1.1 * avg_range

        if up_break and strong_candle:
            e = round(last["high"] + 0.5, 1)
            st = round(min(lows5) - 0.5, 1)
            r = e - st
            tp = round(e + 1.7 * r, 1)
            rr = round((tp - e) / r, 2) if r > 0 else 0
            if rr >= rr_min:
                return normalize_decision({
                    "status": "PROPOSE_TRADE", "side": "BUY", "entry_price": e, "stop_loss": st, "take_profit": tp,
                    "risk_reward_ratio": rr, "invalidation": f"{timeframe} close below {round(min(lows5),1)}",
                    "regime_label": "brk15_breakout_continuation_long",
                    "reason": "15m experiment bounded template: strong breakout continuation long.",
                }, rr_min)

        if dn_break and strong_candle:
            e = round(last["low"] - 0.5, 1)
            st = round(max(highs5) + 0.5, 1)
            r = st - e
            tp = round(e - 1.7 * r, 1)
            rr = round((e - tp) / r, 2) if r > 0 else 0
            if rr >= rr_min:
                return normalize_decision({
                    "status": "PROPOSE_TRADE", "side": "SELL", "entry_price": e, "stop_loss": st, "take_profit": tp,
                    "risk_reward_ratio": rr, "invalidation": f"{timeframe} close above {round(max(highs5),1)}",
                    "regime_label": "brk15_breakout_continuation_short",
                    "reason": "15m experiment bounded template: strong breakout continuation short.",
                }, rr_min)

    return normalize_decision({"status": "WAIT", "regime_label": "structure_no_executable_plan", "reason": "No executable setup."}, rr_min)


async def call_clawbot(scan_payload: dict[str, Any], timeframe: str, rr_min: float):
    prompt = (
        f"Analyze BTC/USD {timeframe} payload and return JSON only: "
        "{\"status\":\"PROPOSE_TRADE|WAIT|REJECT|INSUFFICIENT_DATA\",\"side\":\"BUY|SELL|\",\"entry_price\":0,\"stop_loss\":0,\"take_profit\":0,\"risk_reward_ratio\":0,\"invalidation\":\"\",\"regime_label\":\"\",\"reason\":\"\"}. "
        f"PROPOSE_TRADE requires all fields and rr >= {rr_min}. Paper only.\n"
        + json.dumps(scan_payload, separators=(",", ":"))
    )
    proc = await asyncio.create_subprocess_exec("openclaw", "agent", "--agent", "samy", "--local", "--json", "--message", prompt, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    out, _ = await proc.communicate()
    if proc.returncode != 0:
        return normalize_decision({"status": "INSUFFICIENT_DATA", "regime_label": "scan_error", "reason": "Scan call failed."}, rr_min)
    try:
        txt = (json.loads(out.decode()).get("payloads") or [{}])[0].get("text", "{}")
        d = json.loads(txt)
    except Exception:
        return normalize_decision({"status": "INSUFFICIENT_DATA", "regime_label": "parse_error", "reason": "Parse failed."}, rr_min)
    return normalize_decision(d, rr_min)


def compute_unrealized(p, bid, ask, mode_cfg):
    qty = p["qty"]
    entry = p["entry_fill_price"]
    if p["side"] == "BUY":
        mark = bid
        gross = (mark - entry) * qty
    else:
        mark = ask
        gross = (entry - mark) * qty
    exit_fee_est_info = paper_exit_fee(mode_cfg, mark * qty)
    exit_fee_est = exit_fee_est_info.get("fee", 0.0)
    total_fee_est = p.get("entry_fee", 0.0) + exit_fee_est
    net = gross - total_fee_est
    return {
        "gross_unrealized_pnl": round2(gross),
        "estimated_exit_fee": round2(exit_fee_est),
        "net_unrealized_pnl": round2(net),
        "unrealized_pnl": round2(net),
        "estimated_total_fees": round2(total_fee_est),
    }


def update_position_excursions(p, candle):
    qty = p.get("qty", 1.0)
    entry = p.get("entry_fill_price", 0.0)
    if not entry:
        return
    if p["side"] == "BUY":
        mfe = (candle["high"] - entry) * qty
        mae = (entry - candle["low"]) * qty
    else:
        mfe = (entry - candle["low"]) * qty
        mae = (candle["high"] - entry) * qty
    p["max_favorable_excursion"] = round2(max(p.get("max_favorable_excursion", 0.0), mfe))
    p["max_adverse_excursion"] = round2(max(p.get("max_adverse_excursion", 0.0), mae))


def parse_invalidation_price(invalidation: Any) -> float | None:
    if invalidation is None:
        return None
    if isinstance(invalidation, (int, float)):
        v = float(invalidation)
        return v if v > 0 else None
    s = str(invalidation).strip()
    if not s:
        return None
    try:
        v = float(s)
        return v if v > 0 else None
    except Exception:
        pass
    m = re.search(r"(\d+(?:\.\d+)?)", s)
    if not m:
        return None
    try:
        v = float(m.group(1))
        return v if v > 0 else None
    except Exception:
        return None


def maybe_close(p, candle, slip, mode_cfg):
    side = p["side"]
    price = None
    reason = None

    # 1) Price-hit exits first (existing behavior priority)
    if side == "BUY":
        if candle["low"] <= p["stop_loss"]:
            price = p["stop_loss"] * (1 - slip / 100)
            reason = "STOP_LOSS"
        elif candle["high"] >= p["take_profit"]:
            price = p["take_profit"] * (1 - slip / 100)
            reason = "TAKE_PROFIT"
    else:
        if candle["high"] >= p["stop_loss"]:
            price = p["stop_loss"] * (1 + slip / 100)
            reason = "STOP_LOSS"
        elif candle["low"] <= p["take_profit"]:
            price = p["take_profit"] * (1 + slip / 100)
            reason = "TAKE_PROFIT"

    # 2) Policy exits (disabled by default)
    if reason is None and bool(mode_cfg.get("enable_invalidation_exit", False)):
        inval = parse_invalidation_price(p.get("invalidation"))
        if inval:
            if side == "BUY" and candle["close"] <= inval:
                price = candle["close"] * (1 - slip / 100)
                reason = "INVALIDATION_EXIT"
            elif side == "SELL" and candle["close"] >= inval:
                price = candle["close"] * (1 + slip / 100)
                reason = "INVALIDATION_EXIT"

    if reason is None and bool(mode_cfg.get("enable_time_exit", False)):
        bars_open = int(p.get("bars_open", 0) or 0)
        max_bars_open = int(mode_cfg.get("max_bars_open", 0) or 0)
        max_minutes_open = int(mode_cfg.get("max_minutes_open", 0) or 0)
        hit_bars_limit = max_bars_open > 0 and bars_open >= max_bars_open
        hit_minutes_limit = False
        if max_minutes_open > 0 and p.get("open_time"):
            try:
                opened = datetime.fromisoformat(str(p["open_time"]).replace("Z", "+00:00"))
                age_min = (datetime.now(timezone.utc) - opened).total_seconds() / 60.0
                hit_minutes_limit = age_min >= max_minutes_open
            except Exception:
                hit_minutes_limit = False
        if hit_bars_limit or hit_minutes_limit:
            if side == "BUY":
                price = candle["close"] * (1 - slip / 100)
            else:
                price = candle["close"] * (1 + slip / 100)
            reason = "TIME_EXIT_STALE"

    if reason is None or price is None:
        return None

    if side == "BUY":
        gross_realized = (price - p["entry_fill_price"]) * p["qty"]
    else:
        gross_realized = (p["entry_fill_price"] - price) * p["qty"]

    close_fill_price = round2(price)
    close_notional = close_fill_price * p["qty"]
    close_fee_info = paper_exit_fee(mode_cfg, close_notional)
    close_fee = close_fee_info.get("fee", 0.0)
    total_fees = p.get("entry_fee", 0.0) + close_fee
    net_realized = gross_realized - total_fees

    return {
        **p,
        "status": "PAPER_TRADE_CLOSED",
        "close_reason": reason,
        "close_fill_price": close_fill_price,
        "close_notional": round2(close_notional),
        "close_fee": round2(close_fee),
        "exit_fee": round2(close_fee),
        "close_fee_pct": close_fee_info.get("fee_pct"),
        "close_fee_bps": close_fee_info.get("fee_bps"),
        "close_liquidity": close_fee_info.get("liquidity"),
        "total_fees": round2(total_fees),
        "gross_realized_pnl": round2(gross_realized),
        "net_realized_pnl": round2(net_realized),
        "realized_pnl": round2(net_realized),
        "unrealized_pnl": 0,
        "gross_unrealized_pnl": 0,
        "net_unrealized_pnl": 0,
        "close_time": now_iso(),
    }


def detect_failure_patterns(bucket):
    history = bucket.get("history", [])
    closed = bucket.get("closed_trades", [])
    strategy_entry = bucket.get("strategy_registry_entry") or {}
    no_edge_repeats = len([h for h in history[-100:] if h.get("status") == "WAIT" and "no_edge" in str(h.get("regime_label", ""))])
    tp_missed_reversed = len([
        t for t in closed
        if t.get("close_reason") == "STOP_LOSS"
        and t.get("max_favorable_excursion", 0) > 0
        and t.get("max_favorable_excursion", 0) >= abs(t.get("gross_realized_pnl", 0)) * 0.5
    ])
    fee_drag_destroying_edge = len([
        t for t in closed
        if t.get("gross_realized_pnl", 0) > 0 and t.get("net_realized_pnl", t.get("realized_pnl", 0)) <= 0
    ])
    regime_mismatch = len([
        h for h in history[-100:]
        if h.get("market_regime") and strategy_entry.get("allowed_regimes") and h.get("market_regime") not in strategy_entry.get("allowed_regimes", [])
    ])
    overtrading = max(0, len([h for h in history[-50:] if h.get("status") == "PAPER_TRADE_OPEN"]) - 6)
    undertrading = 1 if no_edge_repeats >= 8 and len([h for h in history[-50:] if h.get("status") == "PAPER_TRADE_OPEN"]) == 0 else 0
    return {
        "tp_missed_then_reversed_to_sl": tp_missed_reversed,
        "no_edge_repeats": no_edge_repeats,
        "fee_drag_destroying_edge": fee_drag_destroying_edge,
        "regime_mismatch": regime_mismatch,
        "overtrading": overtrading,
        "undertrading": undertrading,
    }


def shadow_route_snapshot(current_regime: dict[str, Any]) -> dict[str, Any]:
    candidates = []
    regime = current_regime.get("regime")
    for strategy_key, entry in STRATEGY_REGISTRY.items():
        bucket = store["modes"].get(strategy_key, {})
        perf = (bucket.get("performance_by_regime") or {}).get(regime) or strategy_metrics_bucket()
        status = entry.get("status")
        sample_size = perf.get("sample_size", 0)
        reason_code = "eligible"
        reason = "eligible for shadow routing"
        eligible = True

        if status == "paused":
            eligible = False
            reason_code = "strategy_paused"
            reason = "strategy paused"
        elif regime not in entry.get("allowed_regimes", []):
            eligible = False
            reason_code = "regime_not_allowed"
            reason = "regime not allowed"
        elif sample_size < 1:
            eligible = False
            reason_code = "insufficient_data"
            reason = "insufficient data"

        score = round2(
            perf.get("expectancy", 0.0)
            - abs(perf.get("max_drawdown", 0.0)) * 0.10
            - perf.get("fee_drag_pct", 0.0) * 0.05
            + perf.get("win_rate", 0.0) * 0.02
            + sample_size * 0.03
        ) if eligible else -9999.0

        if eligible and (score is None or not isinstance(score, (int, float))):
            eligible = False
            score = -9999.0
            reason_code = "score_unavailable"
            reason = "score unavailable"

        candidates.append({
            "strategy_key": strategy_key,
            "strategy_family": entry.get("family"),
            "eligible": eligible,
            "score": score,
            "reason": reason,
            "reason_code": reason_code,
            "regime_metrics": perf,
        })
    ranked = sorted(candidates, key=lambda x: x["score"], reverse=True)
    chosen = ranked[0] if ranked and ranked[0]["eligible"] and ranked[0]["score"] > -1000 else None
    return {
        "mode": "shadow_only",
        "regime": regime,
        "selected_strategy": chosen.get("strategy_key") if chosen else None,
        "selected_family": chosen.get("strategy_family") if chosen else None,
        "selected_score": chosen.get("score") if chosen else None,
        "selection_reason": chosen.get("reason") if chosen else "No approved strategy cleared shadow-mode eligibility.",
        "ranked_candidates": ranked,
        "execution_impact": "none",
    }


def strategy_status_for_display(strategy_entry: dict[str, Any], strategy_metrics: dict[str, Any], shadow_routing: dict[str, Any]) -> str:
    if strategy_entry.get("status") == "paused":
        return "paused"
    if strategy_metrics.get("sample_size", 0) < 3:
        return "insufficient_data"
    if strategy_metrics.get("expectancy", 0.0) < 0 or strategy_metrics.get("fee_drag_pct", 0.0) > 100:
        return "probation"
    selected = shadow_routing.get("selected_strategy")
    if selected == strategy_entry.get("strategy_key"):
        return "preferred"
    if any(c.get("strategy_key") == strategy_entry.get("strategy_key") and c.get("eligible") for c in shadow_routing.get("ranked_candidates", [])):
        return "eligible"
    return "insufficient_data"


def summarize_strategy_learning(strategy_key: str, bucket: dict[str, Any]) -> dict[str, Any]:
    perf = bucket.get("performance_by_regime") or regime_metrics_bucket()
    patterns = detect_failure_patterns(bucket)
    ranked = sorted(perf.items(), key=lambda kv: kv[1].get("expectancy", 0.0), reverse=True)
    best_regime = ranked[0][0] if ranked else None
    worst_regime = ranked[-1][0] if ranked else None
    weaknesses = []
    if patterns["tp_missed_then_reversed_to_sl"]:
        weaknesses.append("tp_missed_then_reversed_to_sl")
    if patterns["fee_drag_destroying_edge"]:
        weaknesses.append("fee_drag_destroying_edge")
    if patterns["no_edge_repeats"] >= 5:
        weaknesses.append("no_edge_repeats")
    if patterns["regime_mismatch"]:
        weaknesses.append("regime_mismatch")
    if not weaknesses:
        weaknesses.append("insufficient_confirmed_edge_history")
    next_improvement = "Collect more paper samples before changing logic."
    if patterns["fee_drag_destroying_edge"]:
        next_improvement = "Review exit efficiency and fee-adjusted trade quality in paper mode."
    elif patterns["tp_missed_then_reversed_to_sl"]:
        next_improvement = "Test a controlled exit-only paper experiment after more samples accumulate."
    elif patterns["no_edge_repeats"] >= 5:
        next_improvement = "Review whether this strategy is being used in the wrong regime before tuning entries."
    return {
        "strategy_key": strategy_key,
        "what_works": f"Best observed regime so far: {best_regime}" if best_regime else "No strong edge identified yet.",
        "what_fails": ", ".join(weaknesses),
        "best_regime": best_regime,
        "worst_regime": worst_regime,
        "key_observed_weaknesses": weaknesses,
        "failure_patterns": patterns,
        "next_recommended_controlled_improvement": next_improvement,
    }


def build_metrics_snapshot(closed, openp):
    wins = [x["realized_pnl"] for x in closed if x["realized_pnl"] > 0]
    losses = [x["realized_pnl"] for x in closed if x["realized_pnl"] < 0]
    realized = round2(sum(x["realized_pnl"] for x in closed))
    gross_realized = round2(sum(x.get("gross_realized_pnl", x["realized_pnl"]) for x in closed))
    unrealized = round2(sum(x.get("unrealized_pnl", 0) for x in openp))
    gross_unrealized = round2(sum(x.get("gross_unrealized_pnl", x.get("unrealized_pnl", 0)) for x in openp))
    total_fees = round2(
        sum(x.get("total_fees", x.get("entry_fee", 0.0)) for x in closed)
        + sum(x.get("estimated_total_fees", x.get("entry_fee", 0.0)) for x in openp)
    )
    gross_total_pnl = round2(gross_realized + gross_unrealized)
    expectancy = round2(sum(x["realized_pnl"] for x in closed) / len(closed)) if closed else 0.0
    fee_drag_pct = round2((total_fees / abs(gross_total_pnl) * 100) if gross_total_pnl else 0.0)
    eq, run = [0], 0
    for t in closed:
        run += t["realized_pnl"]
        eq.append(run)
    peak, mdd = 0, 0
    for e in eq:
        peak = max(peak, e)
        mdd = min(mdd, e - peak)
    return {
        "total_trades": len(closed) + len(openp),
        "open_trades": len(openp),
        "closed_trades": len(closed),
        "win_rate": round2((len(wins) / len(closed) * 100) if closed else 0),
        "average_win": round2(sum(wins) / len(wins)) if wins else 0,
        "average_loss": round2(sum(losses) / len(losses)) if losses else 0,
        "expectancy": expectancy,
        "realized_pnl": realized,
        "unrealized_pnl": unrealized,
        "total_fees": total_fees,
        "fee_drag_pct": fee_drag_pct,
        "max_drawdown": round2(mdd),
        "gross_realized_pnl": gross_realized,
        "gross_unrealized_pnl": gross_unrealized,
        "sample_size": len(closed),
    }


def mode_stats(bucket, mode_cfg: dict[str, Any] | None = None):
    closed, openp = bucket["closed_trades"], bucket["open_positions"]
    mode_cfg = mode_cfg or {}
    strategy_metrics = build_metrics_snapshot(closed, openp)
    performance_by_regime = regime_metrics_bucket()
    for regime in REGIME_TYPES:
        regime_closed = [t for t in closed if t.get("market_regime") == regime]
        regime_open = [p for p in openp if p.get("market_regime") == regime]
        performance_by_regime[regime] = build_metrics_snapshot(regime_closed, regime_open)

    bucket["strategy_metrics"] = strategy_metrics
    bucket["performance_by_regime"] = performance_by_regime

    learning_summary = summarize_strategy_learning(bucket.get("strategy_registry_entry", {}).get("strategy_key", "unknown"), bucket)
    return {
        "total_opened": len([h for h in bucket["history"] if h.get("status") == "PAPER_TRADE_OPEN"]),
        "total_closed": len(closed),
        "win_rate": strategy_metrics["win_rate"],
        "average_win": strategy_metrics["average_win"],
        "average_loss": strategy_metrics["average_loss"],
        "expectancy": strategy_metrics["expectancy"],
        "realized_pnl": strategy_metrics["realized_pnl"],
        "gross_realized_pnl": strategy_metrics["gross_realized_pnl"],
        "unrealized_pnl": strategy_metrics["unrealized_pnl"],
        "gross_unrealized_pnl": strategy_metrics["gross_unrealized_pnl"],
        "net_total_pnl": round2(strategy_metrics["realized_pnl"] + strategy_metrics["unrealized_pnl"]),
        "gross_total_pnl": round2(strategy_metrics["gross_realized_pnl"] + strategy_metrics["gross_unrealized_pnl"]),
        "total_fees": strategy_metrics["total_fees"],
        "fee_drag_pct_of_gross_pnl": strategy_metrics["fee_drag_pct"],
        "fee_model": PAPER_FEE_MODEL,
        "fee_assumptions": {
            "entry_fee_bps": mode_cfg.get("fee_bps_entry", 40.0),
            "entry_fee_pct": round2(float(mode_cfg.get("fee_bps_entry", 40.0)) / 100.0),
            "exit_fee_bps": mode_cfg.get("fee_bps_exit", mode_cfg.get("fee_bps_entry", 40.0)),
            "exit_fee_pct": round2(float(mode_cfg.get("fee_bps_exit", mode_cfg.get("fee_bps_entry", 40.0))) / 100.0),
            "liquidity_assumption": "taker",
        },
        "max_drawdown": strategy_metrics["max_drawdown"],
        "strategy_metrics": strategy_metrics,
        "performance_by_regime": performance_by_regime,
        "learning_summary": learning_summary,
    }


async def execute_mode_scan(mode: str):
    cfg = MODE_CONFIGS[mode]
    bucket = store["modes"][mode]
    bucket["strategy_registry_entry"] = STRATEGY_REGISTRY.get(mode)
    timeframe = f"{cfg['interval']}m"
    candles, bid, ask, spread, spread_pct = await fetch_market(cfg["interval"])
    current_regime = classify_market_regime(candles, bid, ask, spread_pct)
    bucket["current_regime"] = current_regime
    payload = {
        "timestamp": now_iso(),
        "market_data": [{"symbol": "BTC/USD", "timeframe": timeframe, "ohlcv": candles, "bid": bid, "ask": ask, "spread": spread, "spread_pct": spread_pct, "slippage_assumption_pct": 0.01}],
        "account_state": {"account_equity": 10000, "cash_available": 10000, "open_positions": [], "active_orders": []},
        "risk_state": {"max_risk_per_trade_pct": 1.0, "max_total_open_risk_pct": 2.0, "max_capital_allocation_pct": 10.0, "stacking_allowed": False},
        "executor_state": {"confirmation_source": "samy_paper_executor", "fills_are_executor_confirmed_only": True, "paper_mode": True},
        "regime_context": current_regime,
        "strategy_registry_entry": bucket["strategy_registry_entry"],
    }
    if KRAKEN_USE_LLM_SCAN:
        d = await call_clawbot(payload, timeframe, cfg["rr_min"])
    else:
        d = normalize_decision({"status": "WAIT", "regime_label": "llm_scan_disabled", "reason": "Kraken no-LLM mode active."}, cfg["rr_min"])

    # Experiment slot must remain a different family from the frozen baseline.
    if mode == "btc_15m_breakout_retest" and d.get("status") == "PROPOSE_TRADE":
        if not str(d.get("regime_label", "")).startswith("brk15_"):
            d = normalize_decision({"status": "WAIT", "regime_label": "brk15_family_mismatch", "reason": "15m experiment family gate blocked non-breakout-retest proposal."}, cfg["rr_min"])

    if d["status"] == "WAIT":
        fb = fallback_construct(candles, cfg["rr_min"], cfg["aggressive"], timeframe)
        if fb["status"] == "PROPOSE_TRADE" or mode == "btc_15m_breakout_retest":
            d = fb

    if mode == "btc_15m_conservative_inverse_v1" and d.get("status") == "PROPOSE_TRADE":
        d = invert_conservative_decision(d, cfg["rr_min"])

    if mode in {"btc_15m_conservative", "btc_15m_conservative_netedge_v1", "btc_15m_conservative_inverse_v1"} and d.get("status") == "PROPOSE_TRADE":
        d = conservative_fee_efficiency_gate(d, mode)

    # Tightening applies ONLY to the 15m experiment mode; 15m baseline remains frozen.
    if mode == "btc_15m_breakout_retest" and d.get("status") == "PROPOSE_TRADE":
        d = aggressive_quality_gate(candles, d, bid, ask, spread_pct)

    d["signal_id"] = d.get("signal_id") or f"{mode}|{payload['timestamp']}|{candles[-1]['time']}"

    history_events: list[dict[str, Any]] = []

    def make_history_row(decision: dict[str, Any], *, ts: str | None = None, decision_time: str | None = None):
        return {
            "timestamp": ts or now_iso(),
            "decision_time": decision_time or now_iso(),
            "mode": mode,
            "strategy_key": mode,
            "strategy_family": bucket["strategy_registry_entry"].get("family") if bucket.get("strategy_registry_entry") else None,
            "market_regime": current_regime.get("regime"),
            "market_regime_confidence": current_regime.get("confidence"),
            "status": decision.get("status"),
            "side": decision.get("side", ""),
            "entry_price": decision.get("entry_price", 0),
            "stop_loss": decision.get("stop_loss", 0),
            "take_profit": decision.get("take_profit", 0),
            "regime_label": decision.get("regime_label", ""),
            "reason": decision.get("reason", ""),
            "risk_reward_ratio": decision.get("risk_reward_ratio", 0),
            "invalidation": decision.get("invalidation", ""),
            "signal_id": decision.get("signal_id", ""),
        }

    # auto execution per-mode lock only
    if d["status"] == "PROPOSE_TRADE":
        history_events.append(make_history_row(d, ts=payload["timestamp"]))
        bucket["notify_user"] = {"timestamp": now_iso(), "message": f"{mode}: PROPOSE_TRADE", "decision": d}
        if d["signal_id"] not in bucket["executed_signal_ids"] and len(bucket["open_positions"]) < MAX_OPEN_POSITIONS_PER_MODE:
            slip = payload["market_data"][0]["slippage_assumption_pct"]
            fill = round2((ask * (1 + slip / 100)) if d["side"] == "BUY" else (bid * (1 - slip / 100)))
            qty = 1.0
            entry_notional = fill * qty
            entry_fee_info = paper_entry_fee(cfg, entry_notional)
            entry_fee = entry_fee_info["fee"]
            initial_exit_fee_info = paper_exit_fee(cfg, entry_notional)
            initial_exit_fee = initial_exit_fee_info["fee"]
            pos = {
                "mode": mode, "strategy_key": mode, "strategy_family": bucket["strategy_registry_entry"].get("family") if bucket.get("strategy_registry_entry") else None,
                "market_regime": current_regime.get("regime"), "market_regime_confidence": current_regime.get("confidence"),
                "signal_id": d["signal_id"], "symbol": "BTC/USD", "timeframe": timeframe, "side": d["side"], "qty": qty,
                "entry_fill_price": fill,
                "entry_notional": round2(entry_notional),
                "entry_fee": round2(entry_fee),
                "fee_model": PAPER_FEE_MODEL,
                "fee_schedule": "mode_fee_bps",
                "entry_fee_bps": entry_fee_info.get("fee_bps"),
                "entry_fee_pct": entry_fee_info.get("fee_pct"),
                "entry_liquidity": entry_fee_info.get("liquidity"),
                "exit_fee_bps_assumption": initial_exit_fee_info.get("fee_bps"),
                "exit_fee_pct_assumption": initial_exit_fee_info.get("fee_pct"),
                "exit_liquidity": initial_exit_fee_info.get("liquidity"),
                "fee_pct": entry_fee_info.get("fee_pct"),
                "stop_loss": d["stop_loss"], "take_profit": d["take_profit"], "invalidation": d["invalidation"],
                "regime_label": d["regime_label"], "reason": d["reason"], "risk_reward_ratio": d["risk_reward_ratio"], "open_time": now_iso(), "open_candle_time": candles[-1]["time"], "last_seen_candle_time": candles[-1]["time"], "bars_open": 0, "close_time": None,
                "status": "PAPER_TRADE_OPEN",
                "gross_unrealized_pnl": 0,
                "estimated_exit_fee": round2(initial_exit_fee),
                "net_unrealized_pnl": round2(-(entry_fee + initial_exit_fee)),
                "unrealized_pnl": round2(-(entry_fee + initial_exit_fee)),
                "realized_pnl": 0,
                "max_favorable_excursion": 0.0, "max_adverse_excursion": 0.0,
            }
            bucket["pending_orders"].append({"timestamp": now_iso(), "mode": mode, "signal_id": d["signal_id"], "status": "QUEUED_TO_PAPER_EXECUTOR", "decision": d})
            bucket["open_positions"].append(pos)
            bucket["executed_signal_ids"].add(d["signal_id"])
            bucket["paper_execution_log"].append({
                "timestamp": now_iso(),
                "mode": mode,
                "action": "AUTO_EXECUTED_PAPER",
                "execution_status": "opened_paper_position",
                "decision": d,
                "entry_fill_price": fill,
                "entry_fee": round2(entry_fee),
                "entry_fee_bps": entry_fee_info.get("fee_bps"),
                "entry_fee_pct": entry_fee_info.get("fee_pct"),
                "entry_liquidity": entry_fee_info.get("liquidity"),
                "exit_fee_bps_assumption": initial_exit_fee_info.get("fee_bps"),
                "exit_liquidity_assumption": initial_exit_fee_info.get("liquidity"),
                "fee_model": PAPER_FEE_MODEL,
            })
            bucket["pending_orders"] = [o for o in bucket["pending_orders"] if o.get("signal_id") != d["signal_id"]]
            history_events.append(make_history_row({"status": "PAPER_TRADE_OPEN", "side": pos["side"], "entry_price": fill, "stop_loss": pos["stop_loss"], "take_profit": pos["take_profit"], "regime_label": pos["regime_label"], "reason": "Auto paper open", "risk_reward_ratio": pos["risk_reward_ratio"], "invalidation": pos["invalidation"], "signal_id": pos["signal_id"]}))
            d = {**d, "status": "PAPER_TRADE_OPEN", "reason": "Auto-executed in paper mode."}
            bucket["notify_user"] = {"timestamp": now_iso(), "message": f"{mode}: PAPER_TRADE_OPEN", "decision": d}

    # close checks
    candle = candles[-1]
    still = []
    for p in bucket["open_positions"]:
        if p.get("last_seen_candle_time") != candle["time"]:
            p["bars_open"] = int(p.get("bars_open", 0) or 0) + 1
            p["last_seen_candle_time"] = candle["time"]
        update_position_excursions(p, candle)
        c = maybe_close(p, candle, payload["market_data"][0]["slippage_assumption_pct"], cfg)
        if c:
            bucket["closed_trades"].append(c)
            bucket["paper_execution_log"].append({"timestamp": now_iso(), "mode": mode, "action": "PAPER_TRADE_CLOSED", "signal_id": c["signal_id"], "close_reason": c["close_reason"], "gross_realized_pnl": c["gross_realized_pnl"], "net_realized_pnl": c["net_realized_pnl"], "realized_pnl": c["realized_pnl"], "total_fees": c["total_fees"]})
            bucket["pending_orders"] = [o for o in bucket["pending_orders"] if o.get("signal_id") != c["signal_id"]]
            history_events.append(make_history_row({"status": "PAPER_TRADE_CLOSED", "side": c["side"], "entry_price": c["entry_fill_price"], "stop_loss": c["stop_loss"], "take_profit": c["take_profit"], "regime_label": c["regime_label"], "reason": f"Closed by {c['close_reason']}", "risk_reward_ratio": c["risk_reward_ratio"], "invalidation": c["invalidation"], "signal_id": c["signal_id"]}))
            d = {"status": "PAPER_TRADE_CLOSED", "side": c["side"], "entry_price": c["entry_fill_price"], "stop_loss": c["stop_loss"], "take_profit": c["take_profit"], "risk_reward_ratio": c["risk_reward_ratio"], "invalidation": c["invalidation"], "regime_label": c["regime_label"], "reason": f"Closed by {c['close_reason']} with realized PnL {c['realized_pnl']}", "signal_id": c["signal_id"]}
            bucket["notify_user"] = {"timestamp": now_iso(), "message": f"{mode}: PAPER_TRADE_CLOSED", "decision": d}
        else:
            u = compute_unrealized(p, bid, ask, cfg)
            p["gross_unrealized_pnl"] = u["gross_unrealized_pnl"]
            p["estimated_exit_fee"] = u["estimated_exit_fee"]
            p["net_unrealized_pnl"] = u["net_unrealized_pnl"]
            p["unrealized_pnl"] = u["unrealized_pnl"]
            p["estimated_total_fees"] = u["estimated_total_fees"]
            still.append(p)
    bucket["open_positions"] = still

    stats = mode_stats(bucket, cfg)
    shadow_routing = shadow_route_snapshot(current_regime)
    strategy_status = strategy_status_for_display(bucket["strategy_registry_entry"] or {}, bucket["strategy_metrics"], shadow_routing)
    latest = {
        **payload,
        "mode": mode,
        "mode_label": cfg["label"],
        "timeframe": timeframe,
        "latest_market_data_time": candles[-1]["time"],
        "latest_scan_time": payload["timestamp"],
        "latest_decision_time": now_iso(),
        "latest_decision": d,
        "triggers": {"upper": TRIGGER_UPPER, "lower": TRIGGER_LOWER},
        "paper_mode": True,
        "max_open_positions_per_mode": MAX_OPEN_POSITIONS_PER_MODE,
        "strategy_registry_entry": bucket["strategy_registry_entry"],
        "strategy_status": strategy_status,
        "current_regime": current_regime,
        "notify_user": bucket["notify_user"],
        "pending_orders": bucket["pending_orders"][-25:],
        "open_positions": bucket["open_positions"],
        "closed_trades": bucket["closed_trades"][-25:],
        "paper_execution_log": bucket["paper_execution_log"][-10:],
        "current_pnl": {
            "realized": round2(sum(t.get("realized_pnl", 0) for t in bucket["closed_trades"])),
            "unrealized": round2(sum(p.get("unrealized_pnl", 0) for p in bucket["open_positions"])),
            "gross_realized": round2(sum(t.get("gross_realized_pnl", t.get("realized_pnl", 0)) for t in bucket["closed_trades"])),
            "gross_unrealized": round2(sum(p.get("gross_unrealized_pnl", p.get("unrealized_pnl", 0)) for p in bucket["open_positions"])),
            "total_fees": round2(
                sum(t.get("total_fees", t.get("entry_fee", 0.0)) for t in bucket["closed_trades"])
                + sum(p.get("estimated_total_fees", p.get("entry_fee", 0.0)) for p in bucket["open_positions"])
            ),
            "fee_drag_pct_of_gross_pnl": stats["fee_drag_pct_of_gross_pnl"],
            "fee_model": PAPER_FEE_MODEL,
            "fee_assumptions": {
                "entry_fee_bps": cfg.get("fee_bps_entry", 40.0),
                "entry_fee_pct": round2(float(cfg.get("fee_bps_entry", 40.0)) / 100.0),
                "exit_fee_bps": cfg.get("fee_bps_exit", cfg.get("fee_bps_entry", 40.0)),
                "exit_fee_pct": round2(float(cfg.get("fee_bps_exit", cfg.get("fee_bps_entry", 40.0))) / 100.0),
                "liquidity_assumption": "taker",
            },
        },
        "mode_stats": stats,
        "strategy_metrics": bucket["strategy_metrics"],
        "performance_by_regime": bucket["performance_by_regime"],
        "learning_summary": stats.get("learning_summary"),
        "shadow_routing": shadow_routing,
        "runtime_info": {
            "agent_runtime_model": "openai-codex/gpt-5.4",
            "gpt_5_4_used_for": "openclaw agent scan proposals via call_clawbot/openclaw agent samy",
            "rule_based_backend_logic": [
                "regime classification",
                "fallback strategy templates",
                "quality gates",
                "paper execution",
                "fee model",
                "shadow routing scores",
                "UI/API state assembly"
            ],
        },
        "execution_limits": {
            "max_open_positions_per_mode": MAX_OPEN_POSITIONS_PER_MODE,
            "paper_only": True,
            "live_trading_enabled": False,
            "kraken_private_order_calls": False,
        },
    }
    bucket["latest"] = latest
    bucket["last_candle_time"] = candles[-1]["time"]
    if not history_events:
        history_events.append(make_history_row(latest["latest_decision"], ts=latest["latest_scan_time"], decision_time=latest["latest_decision_time"]))
    bucket["history"].extend(history_events)
    persist_store()
    return latest


@app.get("/api/state")
async def get_state():
    for m in MODE_CONFIGS.keys():
        if store["modes"][m]["latest"] is None:
            await execute_mode_scan(m)
    return {
        "auto_scan": store["auto_scan"],
        "paper_mode": True,
        "modes": {m: store["modes"][m]["latest"] for m in MODE_CONFIGS.keys()},
        "available_modes": MODE_CONFIGS,
        "strategy_registry": STRATEGY_REGISTRY,
        "regime_types": REGIME_TYPES,
        "hyperliquid_strategy_registry": hyper_track.get_state().get("strategy_registry", {}),
        "hyperliquid_active_strategy_key": hyper_track.get_state().get("active_strategy_key"),
        "runtime_info": {
            "agent_runtime_model": "openai-codex/gpt-5.4",
            "gpt_5_4_used_for": "LLM scan/proposal generation through openclaw agent samy",
            "backend_logic": "rule_based",
            "max_open_positions_per_mode": MAX_OPEN_POSITIONS_PER_MODE,
        },
    }


@app.get("/api/history")
async def get_history(mode: str | None = None):
    if mode and mode in store["modes"]:
        return {"history": store["modes"][mode]["history"][-100:]}
    return {"history": {m: store["modes"][m]["history"][-100:] for m in MODE_CONFIGS.keys()}}


@app.post("/api/run-scan")
async def run_scan(mode: str | None = None):
    if mode and mode in MODE_CONFIGS:
        return {"mode": mode, "state": await execute_mode_scan(mode)}
    return {"modes": {m: await execute_mode_scan(m) for m in MODE_CONFIGS.keys()}}


@app.post("/api/auto-scan")
async def toggle_auto_scan():
    store["auto_scan"] = not store["auto_scan"]
    persist_store()
    return {"auto_scan": store["auto_scan"]}


@app.post("/api/ack-notify/{mode}")
async def ack_notify(mode: str):
    if mode in store["modes"]:
        store["modes"][mode]["notify_user"] = None
        if store["modes"][mode]["latest"]:
            store["modes"][mode]["latest"]["notify_user"] = None
        persist_store()
    return {"ok": True}


@app.get("/api/hyperliquid/state")
async def hyperliquid_state():
    if hyper_track.get_state().get("latest") is None:
        hyper_track.run_scan()
    return hyper_track.get_state()


@app.post("/api/hyperliquid/run-scan")
async def hyperliquid_run_scan():
    return {"state": hyper_track.run_scan()}


@app.post("/api/hyperliquid/mock-open")
async def hyperliquid_mock_open(side: str = "BUY", qty: float = 0.01, leverage: float = 2.0):
    # Explicit manual paper helper only. No exchange route is called.
    return hyper_track.open_paper_position(side=side, qty=qty, leverage=leverage)


if FRONTEND_DIST_DIR.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST_DIR / "assets"), name="frontend-assets")


@app.get("/")
async def frontend_index():
    index = FRONTEND_DIST_DIR / "index.html"
    if index.exists():
        return FileResponse(index)
    return {"ok": True, "message": "Frontend production build not found. Run `npm run build` in btc-paper-ui/frontend or use the dev server."}


@app.on_event("startup")
async def start_auto_scanner():
    load_store()

    async def loop():
        while True:
            try:
                if store["auto_scan"]:
                    for m, cfg in MODE_CONFIGS.items():
                        candles, *_ = await fetch_market(cfg["interval"])
                        ct = candles[-1]["time"]
                        if store["modes"][m]["last_candle_time"] != ct:
                            await execute_mode_scan(m)
                    # Separate Hyperliquid futures paper-training track (mock/public-style only)
                    hyper_track.run_scan()
            except Exception:
                persist_store()
            await asyncio.sleep(20)
    asyncio.create_task(loop())
