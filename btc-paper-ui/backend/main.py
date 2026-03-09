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
}


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


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
    return {
        "status": status,
        "side": decision.get("side", ""),
        "entry_price": decision.get("entry_price", 0),
        "stop_loss": decision.get("stop_loss", 0),
        "take_profit": decision.get("take_profit", 0),
        "risk_reward_ratio": decision.get("risk_reward_ratio", 0),
        "invalidation": decision.get("invalidation", ""),
        "regime_label": decision.get("regime_label", ""),
        "reason": decision.get("reason", ""),
    }


async def call_clawbot(scan_payload: dict[str, Any]) -> dict[str, Any]:
    prompt = (
        "Analyze this BTC/USD 15m Kraken spot paper-trading payload and return JSON only in this exact shape: "
        "{\"status\":\"PROPOSE_TRADE|WAIT|REJECT|INSUFFICIENT_DATA\",\"side\":\"BUY|SELL|\",\"entry_price\":0,\"stop_loss\":0,\"take_profit\":0,\"risk_reward_ratio\":0,\"invalidation\":\"\",\"regime_label\":\"\",\"reason\":\"\"}. "
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
        return normalize_decision({
            "status": "INSUFFICIENT_DATA",
            "regime_label": "scan_error",
            "reason": "Failed to reach Clawbot scan path via Samy.",
        })

    try:
        wrapper = json.loads(out.decode("utf-8"))
        text = (wrapper.get("payloads") or [{}])[0].get("text", "{}")
        decision = json.loads(text)
    except Exception:
        return normalize_decision({
            "status": "INSUFFICIENT_DATA",
            "regime_label": "parse_error",
            "reason": "Clawbot response parse failed.",
        })

    return normalize_decision(decision)


async def build_state():
    candles, bid, ask, spread, spread_pct = await fetch_market()
    scan_payload = build_scan_payload(candles, bid, ask, spread, spread_pct)
    decision = await call_clawbot(scan_payload)
    decision_time = now_iso()

    if decision["status"] == "PROPOSE_TRADE":
        store["notify_user"] = {
            "timestamp": decision_time,
            "message": "PROPOSE_TRADE returned. Notify user before any paper execution step.",
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
    }
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
            "regime_label": s["latest_decision"]["regime_label"],
            "reason": s["latest_decision"]["reason"],
            "risk_reward_ratio": s["latest_decision"]["risk_reward_ratio"],
            "invalidation": s["latest_decision"].get("invalidation", ""),
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
    return {"history": store["history"][-50:]}


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
    latest = store.get("latest") or {}
    decision = latest.get("latest_decision") or {}
    if decision.get("status") != "PROPOSE_TRADE":
        return {"ok": False, "message": "No PROPOSE_TRADE to approve."}

    execution_record = {
        "timestamp": now_iso(),
        "action": "APPROVED_FOR_PAPER_EXECUTOR",
        "executor": "samy_paper_executor",
        "execution_status": "submitted_to_executor_no_fill_confirmation",
        "decision": decision,
    }
    store["paper_execution_log"].append(execution_record)
    store["history"].append({
        "timestamp": execution_record["timestamp"],
        "decision_time": latest.get("latest_decision_time"),
        "status": "APPROVED_PENDING_EXECUTOR",
        "side": decision.get("side", ""),
        "entry_price": decision.get("entry_price", 0),
        "stop_loss": decision.get("stop_loss", 0),
        "take_profit": decision.get("take_profit", 0),
        "regime_label": decision.get("regime_label", ""),
        "reason": "User approved signal for paper executor handoff; no auto-execution in UI/backend.",
        "risk_reward_ratio": decision.get("risk_reward_ratio", 0),
        "invalidation": decision.get("invalidation", ""),
    })
    return {"ok": True, "execution_record": execution_record}


@app.post("/api/proposal/reject")
async def reject_proposal():
    latest = store.get("latest") or {}
    decision = latest.get("latest_decision") or {}
    timestamp = now_iso()
    store["history"].append({
        "timestamp": timestamp,
        "decision_time": latest.get("latest_decision_time"),
        "status": "USER_REJECTED_SIGNAL",
        "side": decision.get("side", ""),
        "entry_price": decision.get("entry_price", 0),
        "stop_loss": decision.get("stop_loss", 0),
        "take_profit": decision.get("take_profit", 0),
        "regime_label": decision.get("regime_label", ""),
        "reason": "User rejected PROPOSE_TRADE signal.",
        "risk_reward_ratio": decision.get("risk_reward_ratio", 0),
        "invalidation": decision.get("invalidation", ""),
    })
    store["notify_user"] = None
    if store.get("latest"):
        store["latest"]["notify_user"] = None
    return {"ok": True, "status": "USER_REJECTED_SIGNAL", "timestamp": timestamp}


@app.on_event("startup")
async def start_auto_scanner():
    async def scanner_loop():
        while True:
            try:
                if store["auto_scan"]:
                    candles, bid, ask, spread, spread_pct = await fetch_market()
                    latest_candle_time = candles[-1]["time"]
                    if store["last_candle_time"] != latest_candle_time:
                        await execute_scan_store()
            except Exception:
                pass
            await asyncio.sleep(30)

    asyncio.create_task(scanner_loop())
