from datetime import datetime, timezone
from typing import Any
import json
import asyncio

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="BTC Paper Backend")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

PAIR = "XBTUSD"
TRIGGER_UPPER = 69513.0
TRIGGER_LOWER = 68698.6

# Paper fee model: fixed percent per fill (taker-style simulation)
PAPER_FEE_MODEL = "fixed_percent_taker"
PAPER_FEE_PCT = 0.40

# 5m experiment controls (change one variable at a time)
AGGR_MAX_SPREAD_PCT = 0.05
AGGR_CHOP_ENTRY_BAND_FRAC = 0.35
AGGR_MIN_RISK_PCT = 0.15
AGGR_MAX_RISK_PCT = 0.90

MODE_CONFIGS = {
    "btc_15m_conservative": {"label": "BTC/USD 15m conservative (frozen baseline)", "interval": 15, "rr_min": 1.5, "aggressive": False},
    "btc_5m_aggressive": {"label": "BTC/USD 5m aggressive", "interval": 5, "rr_min": 1.25, "aggressive": True},
}


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def round2(x: float) -> float:
    return round(float(x), 2)


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
    }


store: dict[str, Any] = {
    "auto_scan": True,
    "modes": {k: mode_bucket() for k in MODE_CONFIGS.keys()},
}


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


def aggressive_quality_gate(candles, d, bid, ask, spread_pct):
    """Extra safety/quality gates for 5m aggressive mode only."""
    if d.get("status") != "PROPOSE_TRADE":
        return d

    side = d.get("side")
    entry = float(d.get("entry_price") or 0)
    stop = float(d.get("stop_loss") or 0)
    rr = float(d.get("risk_reward_ratio") or 0)
    if side not in {"BUY", "SELL"} or entry <= 0 or stop <= 0:
        return normalize_decision({"status": "WAIT", "regime_label": "aggr_filter_invalid_fields", "reason": "Aggressive gate blocked: invalid trade fields."}, 1.25)

    # 1) tighter regime / execution quality filter
    if spread_pct > AGGR_MAX_SPREAD_PCT:
        return normalize_decision({"status": "WAIT", "regime_label": "aggr_filter_spread", "reason": f"Aggressive gate blocked: spread too wide for 5m execution quality (>{AGGR_MAX_SPREAD_PCT}%)."}, 1.25)

    # 2) tighter trade construction: bounded stop distance + stronger R:R floor
    risk_pct = abs(entry - stop) / max(entry, 1) * 100
    if risk_pct < AGGR_MIN_RISK_PCT or risk_pct > AGGR_MAX_RISK_PCT:
        return normalize_decision({"status": "WAIT", "regime_label": "aggr_filter_risk_band", "reason": f"Aggressive gate blocked: stop distance outside {AGGR_MIN_RISK_PCT:.2f}%-{AGGR_MAX_RISK_PCT:.2f}% risk band."}, 1.25)
    if rr < 1.40:
        return normalize_decision({"status": "WAIT", "regime_label": "aggr_filter_rr", "reason": "Aggressive gate blocked: risk/reward below tightened 5m threshold (1.40)."}, 1.25)

    # 3) better entry confirmation: momentum + avoid chasing too far from planned entry
    last, prev = candles[-1], candles[-2]
    if side == "BUY":
        if not (last["close"] >= prev["close"]):
            return normalize_decision({"status": "WAIT", "regime_label": "aggr_filter_confirmation", "reason": "Aggressive gate blocked: missing bullish 2-candle confirmation."}, 1.25)
        if ask > entry * 1.0015:
            return normalize_decision({"status": "WAIT", "regime_label": "aggr_filter_entry_chase", "reason": "Aggressive gate blocked: buy fill would chase too far above planned entry."}, 1.25)
    else:
        if not (last["close"] <= prev["close"]):
            return normalize_decision({"status": "WAIT", "regime_label": "aggr_filter_confirmation", "reason": "Aggressive gate blocked: missing bearish 2-candle confirmation."}, 1.25)
        if bid < entry * 0.9985:
            return normalize_decision({"status": "WAIT", "regime_label": "aggr_filter_entry_chase", "reason": "Aggressive gate blocked: sell fill would chase too far below planned entry."}, 1.25)

    return d


def fallback_construct(candles, rr_min, aggressive, timeframe):
    last, prev = candles[-1], candles[-2]
    highs5 = [c["high"] for c in candles[-5:]]
    lows5 = [c["low"] for c in candles[-5:]]
    highs6 = [c["high"] for c in candles[-6:]]
    lows6 = [c["low"] for c in candles[-6:]]
    ranges = [c["high"] - c["low"] for c in candles[-8:]]
    avg_range = max(0.1, sum(ranges) / len(ranges))

    # 5m aggressive is intentionally a different strategy family: mean-reversion in chop only.
    if aggressive:
        highs10 = [c["high"] for c in candles[-10:]]
        lows10 = [c["low"] for c in candles[-10:]]
        closes10 = [c["close"] for c in candles[-10:]]
        hi10, lo10 = max(highs10), min(lows10)
        width = max(0.1, hi10 - lo10)
        width_pct = (width / max(last["close"], 1)) * 100
        drift_pct = abs(closes10[-1] - closes10[0]) / max(closes10[0], 1) * 100

        # chop-only regime: tight range, low net drift
        if width_pct <= 0.70 and drift_pct <= 0.35:
            lower_band = lo10 + AGGR_CHOP_ENTRY_BAND_FRAC * width
            upper_band = hi10 - AGGR_CHOP_ENTRY_BAND_FRAC * width

            # long reversion from lower band with bullish confirmation
            if last["close"] <= lower_band and last["close"] >= last["open"] and prev["close"] <= prev["open"]:
                e = round(last["high"] + 0.5, 1)
                st = round(min(lows5) - 0.5, 1)
                r = e - st
                tp = round(lo10 + 0.65 * width, 1)
                rr = round((tp - e) / r, 2) if r > 0 else 0
                if rr >= rr_min:
                    return normalize_decision({
                        "status": "PROPOSE_TRADE", "side": "BUY", "entry_price": e, "stop_loss": st, "take_profit": tp,
                        "risk_reward_ratio": rr, "invalidation": f"{timeframe} close below {round(lo10,1)}",
                        "regime_label": "aggr_chop_mean_reversion_long",
                        "reason": "5m family: mean reversion long inside confirmed chop regime.",
                    }, rr_min)

            # short reversion from upper band with bearish confirmation
            if last["close"] >= upper_band and last["close"] <= last["open"] and prev["close"] >= prev["open"]:
                e = round(last["low"] - 0.5, 1)
                st = round(max(highs5) + 0.5, 1)
                r = st - e
                tp = round(hi10 - 0.65 * width, 1)
                rr = round((e - tp) / r, 2) if r > 0 else 0
                if rr >= rr_min:
                    return normalize_decision({
                        "status": "PROPOSE_TRADE", "side": "SELL", "entry_price": e, "stop_loss": st, "take_profit": tp,
                        "risk_reward_ratio": rr, "invalidation": f"{timeframe} close above {round(hi10,1)}",
                        "regime_label": "aggr_chop_mean_reversion_short",
                        "reason": "5m family: mean reversion short inside confirmed chop regime.",
                    }, rr_min)

            return normalize_decision({"status": "WAIT", "regime_label": "aggr_chop_no_edge", "reason": "Chop regime detected but no qualified mean-reversion entry."}, rr_min)

        return normalize_decision({"status": "WAIT", "regime_label": "aggr_filter_not_chop", "reason": "5m strategy family blocks non-chop regime."}, rr_min)

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
            tp = round(e + 1.6 * r, 1)
            rr = round((tp - e) / r, 2) if r > 0 else 0
            if rr >= rr_min:
                return normalize_decision({
                    "status": "PROPOSE_TRADE", "side": "BUY", "entry_price": e, "stop_loss": st, "take_profit": tp,
                    "risk_reward_ratio": rr, "invalidation": f"{timeframe} close below {round(min(lows5),1)}",
                    "regime_label": "aggr_breakout_continuation_long",
                    "reason": "Aggressive bounded template: strong breakout continuation long.",
                }, rr_min)

        if dn_break and strong_candle:
            e = round(last["low"] - 0.5, 1)
            st = round(max(highs5) + 0.5, 1)
            r = st - e
            tp = round(e - 1.6 * r, 1)
            rr = round((e - tp) / r, 2) if r > 0 else 0
            if rr >= rr_min:
                return normalize_decision({
                    "status": "PROPOSE_TRADE", "side": "SELL", "entry_price": e, "stop_loss": st, "take_profit": tp,
                    "risk_reward_ratio": rr, "invalidation": f"{timeframe} close above {round(max(highs5),1)}",
                    "regime_label": "aggr_breakout_continuation_short",
                    "reason": "Aggressive bounded template: strong breakout continuation short.",
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


def compute_unrealized(p, bid, ask):
    qty = p["qty"]
    entry = p["entry_fill_price"]
    fee_pct = p.get("fee_pct", PAPER_FEE_PCT)
    if p["side"] == "BUY":
        mark = bid
        gross = (mark - entry) * qty
    else:
        mark = ask
        gross = (entry - mark) * qty
    exit_fee_est = mark * qty * (fee_pct / 100)
    total_fee_est = p.get("entry_fee", 0.0) + exit_fee_est
    net = gross - total_fee_est
    return {
        "gross_unrealized_pnl": round2(gross),
        "net_unrealized_pnl": round2(net),
        "estimated_total_fees": round2(total_fee_est),
    }


def maybe_close(p, candle, slip):
    side = p["side"]
    if side == "BUY":
        if candle["low"] <= p["stop_loss"]:
            price = p["stop_loss"] * (1 - slip / 100); reason = "STOP_LOSS"
        elif candle["high"] >= p["take_profit"]:
            price = p["take_profit"] * (1 - slip / 100); reason = "TAKE_PROFIT"
        else:
            return None
        gross_realized = (price - p["entry_fill_price"]) * p["qty"]
    else:
        if candle["high"] >= p["stop_loss"]:
            price = p["stop_loss"] * (1 + slip / 100); reason = "STOP_LOSS"
        elif candle["low"] <= p["take_profit"]:
            price = p["take_profit"] * (1 + slip / 100); reason = "TAKE_PROFIT"
        else:
            return None
        gross_realized = (p["entry_fill_price"] - price) * p["qty"]

    close_fill_price = round2(price)
    close_notional = close_fill_price * p["qty"]
    fee_pct = p.get("fee_pct", PAPER_FEE_PCT)
    close_fee = close_notional * (fee_pct / 100)
    total_fees = p.get("entry_fee", 0.0) + close_fee
    net_realized = gross_realized - total_fees

    return {
        **p,
        "status": "PAPER_TRADE_CLOSED",
        "close_reason": reason,
        "close_fill_price": close_fill_price,
        "close_notional": round2(close_notional),
        "close_fee": round2(close_fee),
        "total_fees": round2(total_fees),
        "gross_realized_pnl": round2(gross_realized),
        "net_realized_pnl": round2(net_realized),
        "realized_pnl": round2(net_realized),
        "unrealized_pnl": 0,
        "gross_unrealized_pnl": 0,
        "net_unrealized_pnl": 0,
        "close_time": now_iso(),
    }


def mode_stats(bucket):
    closed, openp = bucket["closed_trades"], bucket["open_positions"]
    wins = [x["realized_pnl"] for x in closed if x["realized_pnl"] > 0]
    losses = [x["realized_pnl"] for x in closed if x["realized_pnl"] < 0]
    realized = round2(sum(x["realized_pnl"] for x in closed))
    gross_realized = round2(sum(x.get("gross_realized_pnl", x["realized_pnl"]) for x in closed))
    unrealized = round2(sum(x.get("unrealized_pnl", 0) for x in openp))
    gross_unrealized = round2(sum(x.get("gross_unrealized_pnl", x.get("unrealized_pnl", 0)) for x in openp))
    total_fees = round2(sum(x.get("total_fees", x.get("entry_fee", 0.0)) for x in closed) + sum(x.get("entry_fee", 0.0) for x in openp))
    gross_total_pnl = round2(gross_realized + gross_unrealized)
    net_total_pnl = round2(realized + unrealized)
    fee_drag_pct_of_gross = round2((total_fees / abs(gross_total_pnl) * 100) if gross_total_pnl != 0 else 0)
    eq, run = [0], 0
    for t in closed:
        run += t["realized_pnl"]; eq.append(run)
    peak, mdd = 0, 0
    for e in eq:
        peak = max(peak, e); mdd = min(mdd, e - peak)
    by = {}
    for t in closed:
        rg = t.get("regime_label", "unknown")
        by.setdefault(rg, {"count": 0, "pnl": 0.0}); by[rg]["count"] += 1; by[rg]["pnl"] = round2(by[rg]["pnl"] + t["realized_pnl"])
    return {
        "total_opened": len([h for h in bucket["history"] if h.get("status") == "PAPER_TRADE_OPEN"]),
        "total_closed": len(closed),
        "win_rate": round2((len(wins) / len(closed) * 100) if closed else 0),
        "average_win": round2(sum(wins) / len(wins)) if wins else 0,
        "average_loss": round2(sum(losses) / len(losses)) if losses else 0,
        "realized_pnl": realized,
        "gross_realized_pnl": gross_realized,
        "unrealized_pnl": unrealized,
        "gross_unrealized_pnl": gross_unrealized,
        "net_total_pnl": net_total_pnl,
        "gross_total_pnl": gross_total_pnl,
        "total_fees": total_fees,
        "fee_drag_pct_of_gross_pnl": fee_drag_pct_of_gross,
        "fee_model": PAPER_FEE_MODEL,
        "fee_pct": PAPER_FEE_PCT,
        "max_drawdown": round2(mdd),
        "performance_by_regime": by,
    }


async def execute_mode_scan(mode: str):
    cfg = MODE_CONFIGS[mode]
    bucket = store["modes"][mode]
    timeframe = f"{cfg['interval']}m"
    candles, bid, ask, spread, spread_pct = await fetch_market(cfg["interval"])
    payload = {
        "timestamp": now_iso(),
        "market_data": [{"symbol": "BTC/USD", "timeframe": timeframe, "ohlcv": candles, "bid": bid, "ask": ask, "spread": spread, "spread_pct": spread_pct, "slippage_assumption_pct": 0.01}],
        "account_state": {"account_equity": 10000, "cash_available": 10000, "open_positions": [], "active_orders": []},
        "risk_state": {"max_risk_per_trade_pct": 1.0, "max_total_open_risk_pct": 2.0, "max_capital_allocation_pct": 10.0, "stacking_allowed": False},
        "executor_state": {"confirmation_source": "samy_paper_executor", "fills_are_executor_confirmed_only": True, "paper_mode": True},
    }
    d = await call_clawbot(payload, timeframe, cfg["rr_min"])

    # 5m experiment must remain a different family from 15m baseline.
    if mode == "btc_5m_aggressive" and d.get("status") == "PROPOSE_TRADE":
        if not str(d.get("regime_label", "")).startswith("aggr_"):
            d = normalize_decision({"status": "WAIT", "regime_label": "aggr_filter_family_mismatch", "reason": "5m family gate blocked non-aggressive regime proposal."}, cfg["rr_min"])

    if d["status"] == "WAIT":
        fb = fallback_construct(candles, cfg["rr_min"], cfg["aggressive"], timeframe)
        if fb["status"] == "PROPOSE_TRADE" or mode == "btc_5m_aggressive":
            d = fb

    # Tightening applies ONLY to 5m aggressive mode; 15m baseline remains frozen.
    if mode == "btc_5m_aggressive" and d.get("status") == "PROPOSE_TRADE":
        d = aggressive_quality_gate(candles, d, bid, ask, spread_pct)

    d["signal_id"] = d.get("signal_id") or f"{mode}|{payload['timestamp']}|{candles[-1]['time']}"

    history_events: list[dict[str, Any]] = []

    def make_history_row(decision: dict[str, Any], *, ts: str | None = None, decision_time: str | None = None):
        return {
            "timestamp": ts or now_iso(),
            "decision_time": decision_time or now_iso(),
            "mode": mode,
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
        if d["signal_id"] not in bucket["executed_signal_ids"] and len(bucket["open_positions"]) == 0:
            slip = payload["market_data"][0]["slippage_assumption_pct"]
            fill = round2((ask * (1 + slip / 100)) if d["side"] == "BUY" else (bid * (1 - slip / 100)))
            qty = 1.0
            entry_notional = fill * qty
            entry_fee = entry_notional * (PAPER_FEE_PCT / 100)
            pos = {
                "mode": mode, "signal_id": d["signal_id"], "symbol": "BTC/USD", "timeframe": timeframe, "side": d["side"], "qty": qty,
                "entry_fill_price": fill, "entry_notional": round2(entry_notional), "entry_fee": round2(entry_fee), "fee_model": PAPER_FEE_MODEL, "fee_pct": PAPER_FEE_PCT,
                "stop_loss": d["stop_loss"], "take_profit": d["take_profit"], "invalidation": d["invalidation"],
                "regime_label": d["regime_label"], "reason": d["reason"], "risk_reward_ratio": d["risk_reward_ratio"], "open_time": now_iso(), "close_time": None,
                "status": "PAPER_TRADE_OPEN", "unrealized_pnl": round2(-entry_fee), "gross_unrealized_pnl": 0, "net_unrealized_pnl": round2(-entry_fee), "realized_pnl": 0,
            }
            bucket["pending_orders"].append({"timestamp": now_iso(), "mode": mode, "signal_id": d["signal_id"], "status": "QUEUED_TO_PAPER_EXECUTOR", "decision": d})
            bucket["open_positions"].append(pos)
            bucket["executed_signal_ids"].add(d["signal_id"])
            bucket["paper_execution_log"].append({"timestamp": now_iso(), "mode": mode, "action": "AUTO_EXECUTED_PAPER", "execution_status": "opened_paper_position", "decision": d, "entry_fill_price": fill, "entry_fee": round2(entry_fee), "fee_pct": PAPER_FEE_PCT, "fee_model": PAPER_FEE_MODEL})
            bucket["pending_orders"] = [o for o in bucket["pending_orders"] if o.get("signal_id") != d["signal_id"]]
            history_events.append(make_history_row({"status": "PAPER_TRADE_OPEN", "side": pos["side"], "entry_price": fill, "stop_loss": pos["stop_loss"], "take_profit": pos["take_profit"], "regime_label": pos["regime_label"], "reason": "Auto paper open", "risk_reward_ratio": pos["risk_reward_ratio"], "invalidation": pos["invalidation"], "signal_id": pos["signal_id"]}))
            d = {**d, "status": "PAPER_TRADE_OPEN", "reason": "Auto-executed in paper mode."}
            bucket["notify_user"] = {"timestamp": now_iso(), "message": f"{mode}: PAPER_TRADE_OPEN", "decision": d}

    # close checks
    candle = candles[-1]
    still = []
    for p in bucket["open_positions"]:
        c = maybe_close(p, candle, payload["market_data"][0]["slippage_assumption_pct"])
        if c:
            bucket["closed_trades"].append(c)
            bucket["paper_execution_log"].append({"timestamp": now_iso(), "mode": mode, "action": "PAPER_TRADE_CLOSED", "signal_id": c["signal_id"], "close_reason": c["close_reason"], "gross_realized_pnl": c["gross_realized_pnl"], "net_realized_pnl": c["net_realized_pnl"], "realized_pnl": c["realized_pnl"], "total_fees": c["total_fees"]})
            bucket["pending_orders"] = [o for o in bucket["pending_orders"] if o.get("signal_id") != c["signal_id"]]
            history_events.append(make_history_row({"status": "PAPER_TRADE_CLOSED", "side": c["side"], "entry_price": c["entry_fill_price"], "stop_loss": c["stop_loss"], "take_profit": c["take_profit"], "regime_label": c["regime_label"], "reason": f"Closed by {c['close_reason']}", "risk_reward_ratio": c["risk_reward_ratio"], "invalidation": c["invalidation"], "signal_id": c["signal_id"]}))
            d = {"status": "PAPER_TRADE_CLOSED", "side": c["side"], "entry_price": c["entry_fill_price"], "stop_loss": c["stop_loss"], "take_profit": c["take_profit"], "risk_reward_ratio": c["risk_reward_ratio"], "invalidation": c["invalidation"], "regime_label": c["regime_label"], "reason": f"Closed by {c['close_reason']} with realized PnL {c['realized_pnl']}", "signal_id": c["signal_id"]}
            bucket["notify_user"] = {"timestamp": now_iso(), "message": f"{mode}: PAPER_TRADE_CLOSED", "decision": d}
        else:
            u = compute_unrealized(p, bid, ask)
            p["gross_unrealized_pnl"] = u["gross_unrealized_pnl"]
            p["net_unrealized_pnl"] = u["net_unrealized_pnl"]
            p["unrealized_pnl"] = u["net_unrealized_pnl"]
            p["estimated_total_fees"] = u["estimated_total_fees"]
            still.append(p)
    bucket["open_positions"] = still

    stats = mode_stats(bucket)
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
            "total_fees": round2(sum(t.get("total_fees", t.get("entry_fee", 0.0)) for t in bucket["closed_trades"]) + sum(p.get("entry_fee", 0.0) for p in bucket["open_positions"])),
            "fee_drag_pct_of_gross_pnl": stats["fee_drag_pct_of_gross_pnl"],
            "fee_model": PAPER_FEE_MODEL,
            "fee_pct": PAPER_FEE_PCT,
        },
        "mode_stats": stats,
    }
    bucket["latest"] = latest
    bucket["last_candle_time"] = candles[-1]["time"]
    if not history_events:
        history_events.append(make_history_row(latest["latest_decision"], ts=latest["latest_scan_time"], decision_time=latest["latest_decision_time"]))
    bucket["history"].extend(history_events)
    return latest


@app.get("/api/state")
async def get_state():
    for m in MODE_CONFIGS.keys():
        if store["modes"][m]["latest"] is None:
            await execute_mode_scan(m)
    return {"auto_scan": store["auto_scan"], "paper_mode": True, "modes": {m: store["modes"][m]["latest"] for m in MODE_CONFIGS.keys()}, "available_modes": MODE_CONFIGS}


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
    return {"auto_scan": store["auto_scan"]}


@app.post("/api/ack-notify/{mode}")
async def ack_notify(mode: str):
    if mode in store["modes"]:
        store["modes"][mode]["notify_user"] = None
        if store["modes"][mode]["latest"]:
            store["modes"][mode]["latest"]["notify_user"] = None
    return {"ok": True}


@app.on_event("startup")
async def start_auto_scanner():
    async def loop():
        while True:
            try:
                if store["auto_scan"]:
                    for m, cfg in MODE_CONFIGS.items():
                        candles, *_ = await fetch_market(cfg["interval"])
                        ct = candles[-1]["time"]
                        if store["modes"][m]["last_candle_time"] != ct:
                            await execute_mode_scan(m)
            except Exception:
                pass
            await asyncio.sleep(20)
    asyncio.create_task(loop())
