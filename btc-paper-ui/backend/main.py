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

MODE_CONFIGS = {
    "btc_15m_conservative": {"label": "BTC/USD 15m conservative", "interval": 15, "rr_min": 1.5, "aggressive": False},
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


def fallback_construct(candles, rr_min, aggressive, timeframe):
    last, prev = candles[-1], candles[-2]
    highs5 = [c["high"] for c in candles[-5:]]
    lows5 = [c["low"] for c in candles[-5:]]
    conf = 1 if aggressive else 2

    if last["close"] < TRIGGER_LOWER and (conf == 1 or prev["close"] < TRIGGER_LOWER):
        e = round(min(last["low"], prev["low"]) - 1, 1); st = round(max(highs5) + 1, 1); r = st - e; tp = round(e - 2 * r, 1); rr = round((e - tp) / r, 2) if r > 0 else 0
        if rr >= rr_min: return normalize_decision({"status": "PROPOSE_TRADE", "side": "SELL", "entry_price": e, "stop_loss": st, "take_profit": tp, "risk_reward_ratio": rr, "invalidation": f"{timeframe} close above {TRIGGER_LOWER}", "regime_label": "bearish_breakdown_continuation", "reason": "Breakdown continuation."}, rr_min)

    low_below = any(c["low"] < TRIGGER_LOWER for c in candles[-8:])
    if low_below and last["close"] > TRIGGER_LOWER and (conf == 1 or prev["close"] > TRIGGER_LOWER):
        e = round(max(highs5) + 1, 1); st = round(min(lows5) - 1, 1); r = e - st; tp = round(e + 2 * r, 1); rr = round((tp - e) / r, 2) if r > 0 else 0
        if rr >= rr_min: return normalize_decision({"status": "PROPOSE_TRADE", "side": "BUY", "entry_price": e, "stop_loss": st, "take_profit": tp, "risk_reward_ratio": rr, "invalidation": f"{timeframe} close below {TRIGGER_LOWER}", "regime_label": "bullish_reclaim_recovery", "reason": "Reclaim recovery."}, rr_min)

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
    return round2((bid - p["entry_fill_price"]) * p["qty"] if p["side"] == "BUY" else (p["entry_fill_price"] - ask) * p["qty"])


def maybe_close(p, candle, slip):
    side = p["side"]
    if side == "BUY":
        if candle["low"] <= p["stop_loss"]:
            price = p["stop_loss"] * (1 - slip / 100); reason = "STOP_LOSS"
        elif candle["high"] >= p["take_profit"]:
            price = p["take_profit"] * (1 - slip / 100); reason = "TAKE_PROFIT"
        else:
            return None
        realized = round2((price - p["entry_fill_price"]) * p["qty"])
    else:
        if candle["high"] >= p["stop_loss"]:
            price = p["stop_loss"] * (1 + slip / 100); reason = "STOP_LOSS"
        elif candle["low"] <= p["take_profit"]:
            price = p["take_profit"] * (1 + slip / 100); reason = "TAKE_PROFIT"
        else:
            return None
        realized = round2((p["entry_fill_price"] - price) * p["qty"])
    return {**p, "status": "PAPER_TRADE_CLOSED", "close_reason": reason, "close_fill_price": round2(price), "realized_pnl": realized, "unrealized_pnl": 0, "close_time": now_iso()}


def mode_stats(bucket):
    closed, openp = bucket["closed_trades"], bucket["open_positions"]
    wins = [x["realized_pnl"] for x in closed if x["realized_pnl"] > 0]
    losses = [x["realized_pnl"] for x in closed if x["realized_pnl"] < 0]
    realized = round2(sum(x["realized_pnl"] for x in closed))
    unrealized = round2(sum(x.get("unrealized_pnl", 0) for x in openp))
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
        "unrealized_pnl": unrealized,
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
    if d["status"] == "WAIT":
        fb = fallback_construct(candles, cfg["rr_min"], cfg["aggressive"], timeframe)
        if fb["status"] == "PROPOSE_TRADE": d = fb
    d["signal_id"] = d.get("signal_id") or f"{mode}|{payload['timestamp']}|{candles[-1]['time']}"

    # auto execution per-mode lock only
    if d["status"] == "PROPOSE_TRADE":
        bucket["notify_user"] = {"timestamp": now_iso(), "message": f"{mode}: PROPOSE_TRADE", "decision": d}
        if d["signal_id"] not in bucket["executed_signal_ids"] and len(bucket["open_positions"]) == 0:
            slip = payload["market_data"][0]["slippage_assumption_pct"]
            fill = round2((ask * (1 + slip / 100)) if d["side"] == "BUY" else (bid * (1 - slip / 100)))
            pos = {
                "mode": mode, "signal_id": d["signal_id"], "symbol": "BTC/USD", "timeframe": timeframe, "side": d["side"], "qty": 1.0,
                "entry_fill_price": fill, "stop_loss": d["stop_loss"], "take_profit": d["take_profit"], "invalidation": d["invalidation"],
                "regime_label": d["regime_label"], "reason": d["reason"], "risk_reward_ratio": d["risk_reward_ratio"], "open_time": now_iso(), "close_time": None,
                "status": "PAPER_TRADE_OPEN", "unrealized_pnl": 0, "realized_pnl": 0,
            }
            bucket["pending_orders"].append({"timestamp": now_iso(), "mode": mode, "signal_id": d["signal_id"], "status": "QUEUED_TO_PAPER_EXECUTOR", "decision": d})
            bucket["open_positions"].append(pos)
            bucket["executed_signal_ids"].add(d["signal_id"])
            bucket["paper_execution_log"].append({"timestamp": now_iso(), "mode": mode, "action": "AUTO_EXECUTED_PAPER", "execution_status": "opened_paper_position", "decision": d, "entry_fill_price": fill})
            bucket["history"].append({"timestamp": now_iso(), "decision_time": now_iso(), "mode": mode, "status": "PAPER_TRADE_OPEN", "side": pos["side"], "entry_price": fill, "stop_loss": pos["stop_loss"], "take_profit": pos["take_profit"], "regime_label": pos["regime_label"], "reason": "Auto paper open", "risk_reward_ratio": pos["risk_reward_ratio"], "invalidation": pos["invalidation"], "signal_id": pos["signal_id"]})
            d = {**d, "status": "PAPER_TRADE_OPEN", "reason": "Auto-executed in paper mode."}
            bucket["notify_user"] = {"timestamp": now_iso(), "message": f"{mode}: PAPER_TRADE_OPEN", "decision": d}

    # close checks
    candle = candles[-1]
    still = []
    for p in bucket["open_positions"]:
        c = maybe_close(p, candle, payload["market_data"][0]["slippage_assumption_pct"])
        if c:
            bucket["closed_trades"].append(c)
            bucket["paper_execution_log"].append({"timestamp": now_iso(), "mode": mode, "action": "PAPER_TRADE_CLOSED", "signal_id": c["signal_id"], "close_reason": c["close_reason"], "realized_pnl": c["realized_pnl"]})
            bucket["history"].append({"timestamp": now_iso(), "decision_time": now_iso(), "mode": mode, "status": "PAPER_TRADE_CLOSED", "side": c["side"], "entry_price": c["entry_fill_price"], "stop_loss": c["stop_loss"], "take_profit": c["take_profit"], "regime_label": c["regime_label"], "reason": f"Closed by {c['close_reason']}", "risk_reward_ratio": c["risk_reward_ratio"], "invalidation": c["invalidation"], "signal_id": c["signal_id"]})
            d = {"status": "PAPER_TRADE_CLOSED", "side": c["side"], "entry_price": c["entry_fill_price"], "stop_loss": c["stop_loss"], "take_profit": c["take_profit"], "risk_reward_ratio": c["risk_reward_ratio"], "invalidation": c["invalidation"], "regime_label": c["regime_label"], "reason": f"Closed by {c['close_reason']} with realized PnL {c['realized_pnl']}", "signal_id": c["signal_id"]}
            bucket["notify_user"] = {"timestamp": now_iso(), "message": f"{mode}: PAPER_TRADE_CLOSED", "decision": d}
        else:
            p["unrealized_pnl"] = compute_unrealized(p, bid, ask)
            still.append(p)
    bucket["open_positions"] = still

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
        "current_pnl": {"realized": round2(sum(t.get("realized_pnl", 0) for t in bucket["closed_trades"])), "unrealized": round2(sum(p.get("unrealized_pnl", 0) for p in bucket["open_positions"]))},
        "mode_stats": mode_stats(bucket),
    }
    bucket["latest"] = latest
    bucket["last_candle_time"] = candles[-1]["time"]
    bucket["history"].append({"timestamp": latest["latest_scan_time"], "decision_time": latest["latest_decision_time"], "mode": mode, "status": latest["latest_decision"].get("status"), "side": latest["latest_decision"].get("side", ""), "entry_price": latest["latest_decision"].get("entry_price", 0), "stop_loss": latest["latest_decision"].get("stop_loss", 0), "take_profit": latest["latest_decision"].get("take_profit", 0), "regime_label": latest["latest_decision"].get("regime_label", ""), "reason": latest["latest_decision"].get("reason", ""), "risk_reward_ratio": latest["latest_decision"].get("risk_reward_ratio", 0), "invalidation": latest["latest_decision"].get("invalidation", ""), "signal_id": latest["latest_decision"].get("signal_id", "")})
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
