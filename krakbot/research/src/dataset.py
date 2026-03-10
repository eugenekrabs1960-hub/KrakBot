from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import pandas as pd
from sqlalchemy import create_engine, text


@dataclass
class ExportConfig:
    database_url: str
    market: str = "SOL/USD"
    timeframe: str = "1m"
    start_ts: Optional[int] = None
    end_ts: Optional[int] = None
    use_market_trades: bool = True


def _build_candles_query(cfg: ExportConfig) -> tuple[str, dict]:
    where = ["market = :market", "timeframe = :timeframe"]
    params: dict = {"market": cfg.market, "timeframe": cfg.timeframe}

    if cfg.start_ts is not None:
        where.append("open_ts >= :start_ts")
        params["start_ts"] = cfg.start_ts
    if cfg.end_ts is not None:
        where.append("open_ts <= :end_ts")
        params["end_ts"] = cfg.end_ts

    query = f"""
        SELECT open_ts, close_ts, open, high, low, close, volume, trade_count
        FROM candles
        WHERE {' AND '.join(where)}
        ORDER BY open_ts ASC
    """
    return query, params


def _build_trade_agg_query(cfg: ExportConfig) -> tuple[str, dict]:
    where = ["market = :market"]
    params: dict = {"market": cfg.market}

    if cfg.start_ts is not None:
        where.append("event_ts >= :start_ts")
        params["start_ts"] = cfg.start_ts
    if cfg.end_ts is not None:
        where.append("event_ts <= :end_ts")
        params["end_ts"] = cfg.end_ts

    query = f"""
        SELECT
            (event_ts / 60000) * 60000 AS bar_ts,
            COUNT(*)::int AS trades_count,
            SUM(qty)::double precision AS trades_qty,
            AVG(price)::double precision AS trades_vwap
        FROM market_trades
        WHERE {' AND '.join(where)}
        GROUP BY 1
        ORDER BY 1 ASC
    """
    return query, params


def export_candles_with_optional_trades(cfg: ExportConfig) -> pd.DataFrame:
    engine = create_engine(cfg.database_url)
    candles_query, candles_params = _build_candles_query(cfg)

    with engine.connect() as conn:
        candles = pd.read_sql(text(candles_query), conn, params=candles_params)

        if candles.empty:
            return candles

        candles = candles.drop_duplicates(subset=["open_ts"], keep="last").copy()
        candles["ts"] = pd.to_datetime(candles["open_ts"], unit="ms", utc=True)
        candles = candles.sort_values("ts").reset_index(drop=True)

        if cfg.use_market_trades:
            trade_query, trade_params = _build_trade_agg_query(cfg)
            trades = pd.read_sql(text(trade_query), conn, params=trade_params)
            if not trades.empty:
                trades = trades.drop_duplicates(subset=["bar_ts"], keep="last").copy()
                candles = candles.merge(
                    trades,
                    how="left",
                    left_on="open_ts",
                    right_on="bar_ts",
                )

    for col, default in [
        ("trades_count", 0),
        ("trades_qty", 0.0),
        ("trades_vwap", candles["close"] if "close" in candles else 0.0),
    ]:
        if col not in candles.columns:
            candles[col] = default
        else:
            candles[col] = candles[col].fillna(default)

    return candles
