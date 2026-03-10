import asyncio
import json
import time
from contextlib import suppress

import websockets
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import SessionLocal
from app.services.checkpoints import load_checkpoint, save_checkpoint
from app.services.market_registry import list_markets
from app.services.ws_hub import ws_hub

KRAKEN_WS_URL = "wss://ws.kraken.com/v2"


class KrakenMarketIngestor:
    def __init__(self):
        self._task: asyncio.Task | None = None
        self._running = False
        self._candles: dict[tuple[str, int], dict] = {}

    async def start(self):
        if self._running:
            return
        # restore checkpoint best-effort
        db = SessionLocal()
        try:
            cp = load_checkpoint(db, 'kraken_ingestor')
            if cp and isinstance(cp, dict):
                # currently only informational, but retained for restart diagnostics
                _ = cp.get('last_event_ts')
        finally:
            db.close()

        self._running = True
        self._task = asyncio.create_task(self._run_loop(), name="kraken-market-ingestor")

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            with suppress(asyncio.CancelledError):
                await self._task

    async def _run_loop(self):
        backoff = 1
        while self._running:
            try:
                await self._connect_and_stream()
                backoff = 1
            except Exception:
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 30)

    async def _connect_and_stream(self):
        async with websockets.connect(KRAKEN_WS_URL, ping_interval=20, ping_timeout=20) as ws:
            symbols = self._enabled_symbols()
            subscribe_trades = {
                "method": "subscribe",
                "params": {"channel": "trade", "symbol": symbols},
            }
            subscribe_book = {
                "method": "subscribe",
                "params": {"channel": "book", "symbol": symbols, "depth": 25},
            }
            await ws.send(json.dumps(subscribe_trades))
            await ws.send(json.dumps(subscribe_book))

            while self._running:
                raw = await ws.recv()
                msg = json.loads(raw)
                await self._handle_message(msg)

    async def _handle_message(self, msg: dict):
        channel = msg.get("channel")
        data = msg.get("data") or []
        if channel == "trade" and data:
            for trade in data:
                event = {
                    "type": "market.trade",
                    "venue": "kraken",
                    "market": trade.get("symbol", "SOL/USD"),
                    "instrument_type": "spot",
                    "ts": int(time.time() * 1000),
                    "payload": trade,
                }
                self._persist_trade(event)
                self._update_candle(event)
                self._save_checkpoint(event.get('ts'))
                await ws_hub.broadcast(event)
        elif channel == "book" and data:
            snap = data[0]
            event = {
                "type": "market.orderbook",
                "venue": "kraken",
                "market": snap.get("symbol", "SOL/USD"),
                "instrument_type": "spot",
                "ts": int(time.time() * 1000),
                "payload": snap,
            }
            self._persist_orderbook(event)
            self._save_checkpoint(event.get('ts'))
            await ws_hub.broadcast(event)

    def _persist_trade(self, event: dict):
        db: Session = SessionLocal()
        try:
            payload = event["payload"]
            db.execute(
                text(
                    """
                    INSERT INTO market_trades(venue, market, instrument_type, side, price, qty, event_ts, raw)
                    VALUES (:venue, :market, :instrument_type, :side, :price, :qty, :event_ts, CAST(:raw AS jsonb))
                    """
                ),
                {
                    "venue": event["venue"],
                    "market": event["market"],
                    "instrument_type": event["instrument_type"],
                    "side": payload.get("side", "unknown"),
                    "price": float(payload.get("price", 0)),
                    "qty": float(payload.get("qty", 0)),
                    "event_ts": int(payload.get("timestamp", event["ts"])),
                    "raw": json.dumps(payload),
                },
            )
            db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()

    def _persist_orderbook(self, event: dict):
        db: Session = SessionLocal()
        try:
            payload = event["payload"]
            db.execute(
                text(
                    """
                    INSERT INTO orderbook_snapshots(venue, market, instrument_type, event_ts, bids, asks, raw)
                    VALUES (:venue, :market, :instrument_type, :event_ts, CAST(:bids AS jsonb), CAST(:asks AS jsonb), CAST(:raw AS jsonb))
                    """
                ),
                {
                    "venue": event["venue"],
                    "market": event["market"],
                    "instrument_type": event["instrument_type"],
                    "event_ts": int(event["ts"]),
                    "bids": json.dumps(payload.get("bids", [])),
                    "asks": json.dumps(payload.get("asks", [])),
                    "raw": json.dumps(payload),
                },
            )
            db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()

    def _update_candle(self, event: dict):
        payload = event["payload"]
        price = float(payload.get("price", 0))
        qty = float(payload.get("qty", 0))
        ts_ms = int(payload.get("timestamp", event["ts"]))
        open_ts = (ts_ms // 60000) * 60000
        key = (event["market"], open_ts)

        candle = self._candles.get(key)
        if candle is None:
            candle = {
                "venue": event["venue"],
                "market": event["market"],
                "instrument_type": event["instrument_type"],
                "timeframe": "1m",
                "open_ts": open_ts,
                "close_ts": open_ts + 59999,
                "open": price,
                "high": price,
                "low": price,
                "close": price,
                "volume": qty,
                "trade_count": 1,
            }
            self._candles[key] = candle
        else:
            candle["high"] = max(candle["high"], price)
            candle["low"] = min(candle["low"], price)
            candle["close"] = price
            candle["volume"] += qty
            candle["trade_count"] += 1

        self._persist_candle(candle)

    def _persist_candle(self, candle: dict):
        db: Session = SessionLocal()
        try:
            db.execute(
                text(
                    """
                    INSERT INTO candles(
                      venue, market, instrument_type, timeframe, open_ts, close_ts,
                      open, high, low, close, volume, trade_count
                    ) VALUES (
                      :venue, :market, :instrument_type, :timeframe, :open_ts, :close_ts,
                      :open, :high, :low, :close, :volume, :trade_count
                    )
                    ON CONFLICT (venue, market, instrument_type, timeframe, open_ts)
                    DO UPDATE SET
                      close_ts = EXCLUDED.close_ts,
                      high = GREATEST(candles.high, EXCLUDED.high),
                      low = LEAST(candles.low, EXCLUDED.low),
                      close = EXCLUDED.close,
                      volume = EXCLUDED.volume,
                      trade_count = EXCLUDED.trade_count
                    """
                ),
                candle,
            )
            db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()

    def _save_checkpoint(self, ts: int | None):
        if ts is None:
            return
        db: Session = SessionLocal()
        try:
            save_checkpoint(db, 'kraken_ingestor', {'last_event_ts': int(ts)})
        finally:
            db.close()

    def _enabled_symbols(self) -> list[str]:
        db: Session = SessionLocal()
        try:
            markets = list_markets(db, enabled_only=True)
            symbols = [m['symbol'] for m in markets if m.get('venue') == 'kraken']
            if symbols:
                return symbols
        except Exception:
            pass
        finally:
            db.close()

        # fallback to env list for bootstrap compatibility
        return [s.strip() for s in settings.enabled_markets.split(',') if s.strip()] or ['SOL/USD']


ingestor = KrakenMarketIngestor()
