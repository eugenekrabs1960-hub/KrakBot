from datetime import datetime, timezone
from typing import Any
import json
import asyncio

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="BTC Paper Backend")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

TRIGGER_UPPER = 69513.0
TRIGGER_LOWER = 68698.6
PAIR = "XBTUSD"

store: dict[str, Any] = {
    "latest": None,
    "history": [],
    "auto_scan": True,
    "notify_user": None,
    "last_candle_time": None,
    "paper_execution_log": [],
    "executed_signal_ids": set(),
    "pending_orders": [],
    "open_positions": [],
    "closed_trades": [],
}


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def round2(x: float) -> float:
    return round(float(x), 2)


async def fetch_market():
    async with httpx.AsyncClient(timeout=20) as client:
        ohlc_r = await client.get(f"https://api.kraken.com/0/public/OHLC?pair={PAIR}&interval=15")
        ticker_r = await client.get(f"https://api.kraken.com/0/public/Ticker?pair={PAIR}")

    ohlc_json = ohlc_r.json()
    ticker_json = ticker_r.json()
    key = next(k for k in ohlc_json["result"].keys() if k != "last")
    rows = ohlc_json["result"][key][-20:]

    candles = []
    for r in rows:
        t = datetime.fromtimestamp(int(r[0]), timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        candles.append(
            {
                "time": t,
                "open": float(r[1]),
                "high": float(r[2]),
                "low": float(r[3]),
                "close": float(r[4]),
                "volume": float(r[6]),
            }
        )

    tk = next(iter(ticker_json["result"].values()))
    bid = float(tk["b"][0])
    ask = float(tk["a"][0])
    spread = ask - bid
    spread_pct = (spread / ((ask + bid) / 2)) * 100

    return candles, bid, ask, spread, spread_pct


def build_scan_payload(candles, bid, ask, spread, spread_pct):
    return {
        "timestamp": now_iso(),
        "market_data": [{
            "symbol": "BTC/USD",
            "timeframe": "15m",
            "ohlcv": candles,
            "bid": bid,
            "ask": ask,
            "spread": spread,
            "spread_pct": spread_pct,
            "slippage_assumption_pct": 0.01,
        }],
        "account_state": {
            "account_equity": 10000,
            "cash_available": 10000,
            "open_positions": [],
            "active_orders": [],
        },
        "risk_state": {
            "max_risk_per_trade_pct": 1.0,
            "max_total_open_risk_pct": 2.0,
            "max_capital_allocation_pct": 10.0,
            "stacking_allowed": False,
        },
        "executor_state": {
            "confirmation_source": "samy_paper_executor",
            "fills_are_executor_confirmed_only": True,
            "paper_mode": True,
        },
    }


def normalize_decision(decision: dict[str, Any]) -> dict[str, Any]:
    status = decision.get("status", "INSUFFICIENT_DATA")
    if status not in {"PROPOSE_TRADE", "WAIT", "REJECT", "INSUFFICIENT_DATA"}:
        status = "INSUFFICIENT_DATA"

    normalized = {
        "status": status,
        "side": decision.get("side", ""),
        "entry_price": decision.get("entry_price", 0),
        "stop_loss": decision.get("stop_loss", 0),
        "take_profit": decision.get("take_profit", 0),
        "risk_reward_ratio": decision.get("risk_reward_ratio", 0),
        "invalidation": decision.get("invalidation", ""),
        "regime_label": decision.get("regime_label", ""),
        "reason": decision.get("reason", ""),
        "signal_id": decision.get("signal_id", ""),
    }

    if normalized["status"] == "PROPOSE_TRADE":
        required_ok = all([
            normalized["side"] in {"BUY", "SELL"},
            isinstance(normalized["entry_price"], (int, float)) and normalized["entry_price"] > 0,
            isinstance(normalized["stop_loss"], (int, float)) and normalized["stop_loss"] > 0,
            isinstance(normalized["take_profit"], (int, float)) and normalized["take_profit"] > 0,
            isinstance(normalized["risk_reward_ratio"], (int, float)) and normalized["risk_reward_ratio"] >= 1.5,
            isinstance(normalized["invalidation"], str) and normalized["invalidation"].strip() != "",
            isinstance(normalized["regime_label"], str) and normalized["regime_label"].strip() != "",
            isinstance(normalized["reason"], str) and normalized["reason"].strip() != "",
        ])
        if not required_ok:
            normalized.update({
                "status": "WAIT",
                "reason": "Clawbot did not provide full executable trade fields; keeping WAIT.",
                "side": "",
                "entry_price": 0,
                "stop_loss": 0,
                "take_profit": 0,
                "risk_reward_ratio": 0,
                "invalidation": "",
            })

    return normalized


def construct_trade_from_structure(candles: list[dict[str, Any]]) -> dict[str, Any]:
    if len(candles) < 8:
        return normalize_decision({"status": "WAIT", "regime_label": "insufficient_structure", "reason": "Not enough candles for setup construction."})

    last = candles[-1]
    prev = candles[-2]
    highs5 = [c["high"] for c in candles[-5:]]
    lows5 = [c["low"] for c in candles[-5:]]
    highs6 = [c["high"] for c in candles[-6:]]
    lows6 = [c["low"] for c in candles[-6:]]

    if last["close"] < TRIGGER_LOWER and prev["close"] < TRIGGER_LOWER:
        entry = round(min(last["low"], prev["low"]) - 1.0, 1)
        stop = round(max(highs5) + 1.0, 1)
        risk = stop - entry
        tp = round(entry - (2.0 * risk), 1)
        rr = round((entry - tp) / risk, 2) if risk > 0 else 0
        if risk > 0 and rr >= 1.5:
            return normalize_decision({
                "status": "PROPOSE_TRADE", "side": "SELL", "entry_price": entry,
                "stop_loss": stop, "take_profit": tp, "risk_reward_ratio": rr,
                "invalidation": f"15m close above {TRIGGER_LOWER}",
                "regime_label": "bearish_breakdown_continuation",
                "reason": "Two consecutive closes below breakdown trigger with continuation structure.",
            })

    recent_low_below = any(c["low"] < TRIGGER_LOWER for c in candles[-8:])
    if recent_low_below and last["close"] > TRIGGER_LOWER and prev["close"] > TRIGGER_LOWER:
        entry = round(max(highs5) + 1.0, 1)
        stop = round(min(lows5) - 1.0, 1)
        risk = entry - stop
        tp = round(entry + (2.0 * risk), 1)
        rr = round((tp - entry) / risk, 2) if risk > 0 else 0
        if risk > 0 and rr >= 1.5:
            return normalize_decision({
                "status": "PROPOSE_TRADE", "side": "BUY", "entry_price": entry,
                "stop_loss": stop, "take_profit": tp, "risk_reward_ratio": rr,
                "invalidation": f"15m close back below {TRIGGER_LOWER}",
                "regime_label": "bullish_reclaim_recovery",
                "reason": "Reclaim above breakdown level with follow-through closes.",
            })

    if prev["high"] >= TRIGGER_UPPER * 0.997 and last["close"] < prev["close"]:
        entry = round(last["low"] - 1.0, 1)
        stop = round(max(highs5) + 1.0, 1)
        risk = stop - entry
        tp = round(entry - (1.8 * risk), 1)
        rr = round((entry - tp) / risk, 2) if risk > 0 else 0
        if risk > 0 and rr >= 1.5:
            return normalize_decision({
                "status": "PROPOSE_TRADE", "side": "SELL", "entry_price": entry,
                "stop_loss": stop, "take_profit": tp, "risk_reward_ratio": rr,
                "invalidation": f"15m close above {TRIGGER_UPPER}",
                "regime_label": "rebound_into_resistance",
                "reason": "Rejection after rebound toward resistance zone.",
            })

    rng = max(highs6) - min(lows6)
    if last["close"] > max(highs6[:-1]) and rng / max(last["close"], 1) < 0.006:
        entry = round(max(highs6) + 1.0, 1)
        stop = round(min(lows6) - 1.0, 1)
        risk = entry - stop
        tp = round(entry + (1.8 * risk), 1)
        rr = round((tp - entry) / risk, 2) if risk > 0 else 0
        if risk > 0 and rr >= 1.5:
            return normalize_decision({
                "status": "PROPOSE_TRADE", "side": "BUY", "entry_price": entry,
                "stop_loss": stop, "take_profit": tp, "risk_reward_ratio": rr,
                "invalidation": f"15m close below {round(min(lows6),1)}",
                "regime_label": "consolidation_breakout",
                "reason": "Compression followed by upside breakout trigger.",
            })

    return normalize_decision({
        "status": "WAIT",
        "regime_label": "structure_no_executable_plan",
        "reason": "Structure detected but executable trade levels could not be derived with required R:R.",
    })


async def call_clawbot(scan_payload: dict[str, Any]) -> dict[str, Any]:
    prompt = (
        "Analyze this BTC/USD 15m Kraken spot paper-trading payload and return JSON only in this exact shape: "
        "{\"status\":\"PROPOSE_TRADE|WAIT|REJECT|INSUFFICIENT_DATA\",\"side\":\"BUY|SELL|\",\"entry_price\":0,\"stop_loss\":0,\"take_profit\":0,\"risk_reward_ratio\":0,\"invalidation\":\"\",\"regime_label\":\"\",\"reason\":\"\"}. "
        "PROPOSE_TRADE is allowed only when all executable fields are present and risk_reward_ratio >= 1.5. "
        "If structure exists but executable fields cannot be derived, return WAIT. "
        "Paper mode only. No live trading. No execution. Do not invent missing values. Payload:\n"
        + json.dumps(scan_payload, separators=(",", ":"))
    )

    proc = await asyncio.create_subprocess_exec(
        "openclaw", "agent", "--agent", "samy", "--local", "--json", "--message", prompt,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    out, _ = await proc.communicate()
    if proc.returncode != 0:
        return normalize_decision({"status": "INSUFFICIENT_DATA", "regime_label": "scan_error", "reason": "Failed to reach Clawbot scan path via Samy."})

    try:
        wrapper = json.loads(out.decode("utf-8"))
        text = (wrapper.get("payloads") or [{}])[0].get("text", "{}")
        decision = json.loads(text)
    except Exception:
        return normalize_decision({"status": "INSUFFICIENT_DATA", "regime_label": "parse_error", "reason": "Clawbot response parse failed."})

    return normalize_decision(decision)


def compute_unrealized(position: dict[str, Any], bid: float, ask: float) -> float:
    qty = position["qty"]
    entry = position["entry_fill_price"]
    if position["side"] == "BUY":
        return round2((bid - entry) * qty)
    return round2((entry - ask) * qty)


def maybe_close_position(position: dict[str, Any], candle: dict[str, Any], bid: float, ask: float, slip_pct: float):
    side = position["side"]
    hit = None
    close_price = None

    if side == "BUY":
        if candle["low"] <= position["stop_loss"]:
            hit = "STOP_LOSS"
            close_price = position["stop_loss"] * (1 - slip_pct / 100)
        elif candle["high"] >= position["take_profit"]:
            hit = "TAKE_PROFIT"
            close_price = position["take_profit"] * (1 - slip_pct / 100)
    else:
        if candle["high"] >= position["stop_loss"]:
            hit = "STOP_LOSS"
            close_price = position["stop_loss"] * (1 + slip_pct / 100)
        elif candle["low"] <= position["take_profit"]:
            hit = "TAKE_PROFIT"
            close_price = position["take_profit"] * (1 + slip_pct / 100)

    if not hit:
        return None

    close_fill = round2(close_price)
    qty = position["qty"]
    if side == "BUY":
        realized = round2((close_fill - position["entry_fill_price"]) * qty)
    else:
        realized = round2((position["entry_fill_price"] - close_fill) * qty)

    closed = {
        **position,
        "status": "PAPER_TRADE_CLOSED",
        "close_reason": hit,
        "close_fill_price": close_fill,
        "realized_pnl": realized,
        "close_time": now_iso(),
        "unrealized_pnl": 0,
    }
    return closed


def auto_execute_proposed_trade(latest: dict[str, Any]):
    decision = latest.get("latest_decision", {})
    if decision.get("status") != "PROPOSE_TRADE":
        return latest

    signal_id = decision.get("signal_id")
    if not signal_id:
        return latest
    if signal_id in store["executed_signal_ids"]:
        return latest

    md = latest["market_data"][0]
    bid, ask = md["bid"], md["ask"]
    slip = md.get("slippage_assumption_pct", 0.01)

    qty = 1.0
    if decision["side"] == "BUY":
        entry_fill = round2(ask * (1 + slip / 100))
    else:
        entry_fill = round2(bid * (1 - slip / 100))

    position = {
        "signal_id": signal_id,
        "symbol": "BTC/USD",
        "timeframe": "15m",
        "side": decision["side"],
        "qty": qty,
        "entry_fill_price": entry_fill,
        "stop_loss": decision["stop_loss"],
        "take_profit": decision["take_profit"],
        "invalidation": decision["invalidation"],
        "regime_label": decision["regime_label"],
        "reason": decision["reason"],
        "risk_reward_ratio": decision["risk_reward_ratio"],
        "open_time": now_iso(),
        "close_time": None,
        "status": "PAPER_TRADE_OPEN",
        "unrealized_pnl": 0,
        "realized_pnl": 0,
    }

    store["pending_orders"].append({
        "timestamp": now_iso(),
        "signal_id": signal_id,
        "status": "QUEUED_TO_PAPER_EXECUTOR",
        "decision": decision,
    })
    store["open_positions"].append(position)
    store["executed_signal_ids"].add(signal_id)
    store["paper_execution_log"].append({
        "timestamp": now_iso(),
        "action": "AUTO_EXECUTED_PAPER",
        "executor": "samy_paper_executor",
        "execution_status": "opened_paper_position",
        "decision": decision,
        "entry_fill_price": entry_fill,
    })
    store["history"].append({
        "timestamp": now_iso(),
        "decision_time": latest.get("latest_decision_time"),
        "status": "PAPER_TRADE_OPEN",
        "side": position["side"],
        "entry_price": position["entry_fill_price"],
        "stop_loss": position["stop_loss"],
        "take_profit": position["take_profit"],
        "regime_label": position["regime_label"],
        "reason": "Auto-handled from PROPOSE_TRADE to paper executor open.",
        "risk_reward_ratio": position["risk_reward_ratio"],
        "invalidation": position["invalidation"],
    })

    latest["latest_decision"] = {
        **decision,
        "status": "PAPER_TRADE_OPEN",
        "reason": "Auto-executed in paper mode via paper executor flow.",
    }
    latest["latest_decision_time"] = now_iso()
    store["notify_user"] = {
        "timestamp": now_iso(),
        "message": "PAPER_TRADE_OPEN",
        "decision": latest["latest_decision"],
    }
    latest["notify_user"] = store["notify_user"]
    return latest


def update_positions_with_latest_candle(latest: dict[str, Any]):
    md = latest["market_data"][0]
    candle = md["ohlcv"][-1]
    bid, ask = md["bid"], md["ask"]
    slip = md.get("slippage_assumption_pct", 0.01)

    still_open = []
    for pos in store["open_positions"]:
        closed = maybe_close_position(pos, candle, bid, ask, slip)
        if closed:
            store["closed_trades"].append(closed)
            store["paper_execution_log"].append({
                "timestamp": now_iso(),
                "action": "PAPER_TRADE_CLOSED",
                "signal_id": pos["signal_id"],
                "close_reason": closed["close_reason"],
                "realized_pnl": closed["realized_pnl"],
            })
            store["history"].append({
                "timestamp": now_iso(),
                "decision_time": latest.get("latest_decision_time"),
                "status": "PAPER_TRADE_CLOSED",
                "side": closed["side"],
                "entry_price": closed["entry_fill_price"],
                "stop_loss": closed["stop_loss"],
                "take_profit": closed["take_profit"],
                "regime_label": closed["regime_label"],
                "reason": f"Closed by {closed['close_reason']}",
                "risk_reward_ratio": closed["risk_reward_ratio"],
                "invalidation": closed["invalidation"],
            })
            latest["latest_decision"] = {
                "status": "PAPER_TRADE_CLOSED",
                "side": closed["side"],
                "entry_price": closed["entry_fill_price"],
                "stop_loss": closed["stop_loss"],
                "take_profit": closed["take_profit"],
                "risk_reward_ratio": closed["risk_reward_ratio"],
                "invalidation": closed["invalidation"],
                "regime_label": closed["regime_label"],
                "reason": f"Closed by {closed['close_reason']} with realized PnL {closed['realized_pnl']}",
                "signal_id": closed["signal_id"],
            }
            latest["latest_decision_time"] = now_iso()
            store["notify_user"] = {
                "timestamp": now_iso(),
                "message": "PAPER_TRADE_CLOSED",
                "decision": latest["latest_decision"],
            }
            latest["notify_user"] = store["notify_user"]
        else:
            pos["unrealized_pnl"] = compute_unrealized(pos, bid, ask)
            still_open.append(pos)

    store["open_positions"] = still_open
    latest["open_positions"] = store["open_positions"]
    latest["closed_trades"] = store["closed_trades"][-25:]
    latest["pending_orders"] = store["pending_orders"][-25:]
    latest["current_pnl"] = {
        "unrealized": round2(sum(p.get("unrealized_pnl", 0) for p in store["open_positions"])),
        "realized": round2(sum(t.get("realized_pnl", 0) for t in store["closed_trades"])),
    }
    return latest


async def build_state():
    candles, bid, ask, spread, spread_pct = await fetch_market()
    scan_payload = build_scan_payload(candles, bid, ask, spread, spread_pct)
    decision = await call_clawbot(scan_payload)
    if decision.get("status") == "WAIT":
        fallback = construct_trade_from_structure(candles)
        if fallback.get("status") == "PROPOSE_TRADE":
            decision = fallback
    decision_time = now_iso()
    if not decision.get("signal_id"):
        decision["signal_id"] = f"{scan_payload['timestamp']}|{candles[-1]['time']}"

    if decision["status"] == "PROPOSE_TRADE":
        store["notify_user"] = {
            "timestamp": decision_time,
            "message": "PROPOSE_TRADE returned. Auto paper-execution flow will process.",
            "decision": decision,
        }

    payload = {
        **scan_payload,
        "latest_market_data_time": candles[-1]["time"],
        "latest_scan_time": scan_payload["timestamp"],
        "latest_decision_time": decision_time,
        "latest_decision": decision,
        "triggers": {"upper": TRIGGER_UPPER, "lower": TRIGGER_LOWER},
        "paper_mode": True,
        "notify_user": store.get("notify_user"),
        "paper_execution_log": store["paper_execution_log"][-10:],
        "pending_orders": store["pending_orders"][-25:],
        "open_positions": store["open_positions"],
        "closed_trades": store["closed_trades"][-25:],
        "current_pnl": {
            "unrealized": round2(sum(p.get("unrealized_pnl", 0) for p in store["open_positions"])),
            "realized": round2(sum(t.get("realized_pnl", 0) for t in store["closed_trades"])),
        },
    }

    payload = auto_execute_proposed_trade(payload)
    payload = update_positions_with_latest_candle(payload)
    return payload


async def execute_scan_store():
    s = await build_state()
    store["latest"] = s
    store["last_candle_time"] = s["latest_market_data_time"]
    store["history"].append(
        {
            "timestamp": s["timestamp"],
            "decision_time": s["latest_decision_time"],
            "status": s["latest_decision"]["status"],
            "side": s["latest_decision"].get("side", ""),
            "entry_price": s["latest_decision"].get("entry_price", 0),
            "stop_loss": s["latest_decision"].get("stop_loss", 0),
            "take_profit": s["latest_decision"].get("take_profit", 0),
            "regime_label": s["latest_decision"].get("regime_label", ""),
            "reason": s["latest_decision"].get("reason", ""),
            "risk_reward_ratio": s["latest_decision"].get("risk_reward_ratio", 0),
            "invalidation": s["latest_decision"].get("invalidation", ""),
            "signal_id": s["latest_decision"].get("signal_id", ""),
        }
    )
    return s


@app.get("/api/state")
async def get_state():
    if not store["latest"]:
        await execute_scan_store()
    return {**store["latest"], "auto_scan": store["auto_scan"]}


@app.get("/api/history")
async def get_history():
    return {"history": store["history"][-100:]}


@app.post("/api/run-scan")
async def run_scan():
    return await execute_scan_store()


@app.post("/api/auto-scan")
async def toggle_auto_scan():
    store["auto_scan"] = not store["auto_scan"]
    return {"auto_scan": store["auto_scan"]}


@app.post("/api/ack-notify")
async def ack_notify():
    store["notify_user"] = None
    if store.get("latest"):
        store["latest"]["notify_user"] = None
    return {"ok": True}


@app.post("/api/proposal/approve")
async def approve_proposal():
    return {"ok": False, "message": "Manual approve disabled: auto paper execution flow is enabled."}


@app.post("/api/proposal/reject")
async def reject_proposal():
    return {"ok": False, "message": "Manual reject disabled: auto paper execution flow is enabled."}


@app.on_event("startup")
async def start_auto_scanner():
    async def scanner_loop():
        while True:
            try:
                if store["auto_scan"]:
                    candles, _, _, _, _ = await fetch_market()
                    latest_candle_time = candles[-1]["time"]
                    if store["last_candle_time"] != latest_candle_time:
                        await execute_scan_store()
            except Exception:
                pass
            await asyncio.sleep(30)

    asyncio.create_task(scanner_loop())
