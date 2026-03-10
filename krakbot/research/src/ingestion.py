from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import urlopen

import pandas as pd

from src.dataset import ExportConfig, export_candles_with_optional_trades


REQUIRED_CANONICAL_COLS = ["ts", "open", "high", "low", "close", "volume"]


@dataclass
class SourceConfig:
    source: str
    timeframe: str = "1m"
    market: str = "SOL/USD"


def timeframe_to_minutes(tf: str) -> int:
    tf = str(tf).strip().lower()
    if tf.endswith("m"):
        return int(tf[:-1])
    if tf.endswith("h"):
        return int(tf[:-1]) * 60
    if tf.endswith("d"):
        return int(tf[:-1]) * 60 * 24
    raise ValueError(f"Unsupported timeframe: {tf}")


def _symbol_to_kraken_pair(market: str) -> str:
    return market.replace("/", "")


def _ensure_canonical(df: pd.DataFrame, timeframe: str) -> pd.DataFrame:
    out = df.copy()
    if "ts" not in out.columns:
        raise ValueError("Normalized dataset must include 'ts'")

    out["ts"] = pd.to_datetime(out["ts"], utc=True)
    out = out.sort_values("ts").reset_index(drop=True)

    for col in ["open", "high", "low", "close", "volume"]:
        out[col] = pd.to_numeric(out[col], errors="coerce")

    if "open_ts" not in out.columns:
        out["open_ts"] = (out["ts"].astype("int64") // 10**6).astype("int64")

    interval_ms = timeframe_to_minutes(timeframe) * 60_000
    if "close_ts" not in out.columns:
        out["close_ts"] = out["open_ts"] + interval_ms - 1

    if "trade_count" not in out.columns:
        out["trade_count"] = 0

    for col, default in [("trades_count", 0), ("trades_qty", 0.0), ("trades_vwap", out["close"])]:
        if col not in out.columns:
            out[col] = default
        else:
            out[col] = out[col].fillna(default)

    return out


def load_from_local_db(dataset_cfg: dict[str, Any], database_url: str) -> pd.DataFrame:
    export_cfg = ExportConfig(
        database_url=database_url,
        market=dataset_cfg.get("market", "SOL/USD"),
        timeframe=dataset_cfg.get("timeframe", "1m"),
        start_ts=dataset_cfg.get("start_ts"),
        end_ts=dataset_cfg.get("end_ts"),
        use_market_trades=bool(dataset_cfg.get("use_market_trades", True)),
    )
    df = export_candles_with_optional_trades(export_cfg)
    return _ensure_canonical(df, timeframe=export_cfg.timeframe)


def load_from_external_csv(research_dir: Path, dataset_cfg: dict[str, Any]) -> pd.DataFrame:
    csv_cfg = dataset_cfg.get("external_csv", {})
    raw_path = Path(csv_cfg.get("path", "data/raw/ohlcv.csv"))
    if not raw_path.is_absolute():
        raw_path = (research_dir / raw_path).resolve()

    mapping = csv_cfg.get("column_mapping", {})
    tz_name = csv_cfg.get("timezone", "UTC")

    source_df = pd.read_csv(raw_path)

    ts_col = mapping.get("timestamp", "timestamp")
    rename_map = {
        ts_col: "ts",
        mapping.get("open", "open"): "open",
        mapping.get("high", "high"): "high",
        mapping.get("low", "low"): "low",
        mapping.get("close", "close"): "close",
        mapping.get("volume", "volume"): "volume",
    }

    df = source_df.rename(columns=rename_map)
    missing = [c for c in REQUIRED_CANONICAL_COLS if c not in df.columns]
    if missing:
        raise ValueError(f"CSV missing required mapped columns: {missing}")

    parsed = pd.to_datetime(df["ts"], errors="coerce")
    if str(parsed.dt.tz) == "None":
        parsed = parsed.dt.tz_localize(tz_name)
    df["ts"] = parsed.dt.tz_convert("UTC")

    normalized = _ensure_canonical(df, timeframe=dataset_cfg.get("timeframe", "1m"))
    return normalized


def load_from_external_api(research_dir: Path, dataset_cfg: dict[str, Any]) -> pd.DataFrame:
    api_cfg = dataset_cfg.get("external_api", {})
    provider = api_cfg.get("provider", "kraken")
    if provider != "kraken":
        raise ValueError(f"Unsupported provider: {provider}")

    market = dataset_cfg.get("market", "SOL/USD")
    timeframe = dataset_cfg.get("timeframe", "1m")
    interval_m = timeframe_to_minutes(timeframe)
    pair = api_cfg.get("pair", _symbol_to_kraken_pair(market))
    since = api_cfg.get("since")
    limit = int(api_cfg.get("limit", 720))

    if limit < 1 or limit > 720:
        raise ValueError("external_api.limit must be between 1 and 720 for Kraken")

    params = {"pair": pair, "interval": interval_m}
    if since:
        params["since"] = int(since)

    url = f"https://api.kraken.com/0/public/OHLC?{urlencode(params)}"
    with urlopen(url, timeout=30) as resp:
        payload = json.loads(resp.read().decode("utf-8"))

    if payload.get("error"):
        raise RuntimeError(f"Kraken API error: {payload['error']}")

    result = payload.get("result", {})
    rows = result.get(pair) or next((v for k, v in result.items() if k != "last"), [])
    rows = rows[-limit:]

    cols = ["open_time", "open", "high", "low", "close", "vwap", "volume", "count"]
    raw_df = pd.DataFrame(rows, columns=cols)

    raw_dir = research_dir / "data" / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    stamp = int(time.time())
    raw_path = raw_dir / f"kraken_ohlc_{pair}_{timeframe}_{stamp}.csv"
    raw_df.to_csv(raw_path, index=False)

    normalized = pd.DataFrame(
        {
            "ts": pd.to_datetime(raw_df["open_time"], unit="s", utc=True),
            "open": pd.to_numeric(raw_df["open"], errors="coerce"),
            "high": pd.to_numeric(raw_df["high"], errors="coerce"),
            "low": pd.to_numeric(raw_df["low"], errors="coerce"),
            "close": pd.to_numeric(raw_df["close"], errors="coerce"),
            "volume": pd.to_numeric(raw_df["volume"], errors="coerce"),
            "trade_count": pd.to_numeric(raw_df["count"], errors="coerce").fillna(0).astype(int),
        }
    )

    return _ensure_canonical(normalized, timeframe=timeframe)


def load_dataset_by_source(research_dir: Path, dataset_cfg: dict[str, Any], database_url: str | None) -> pd.DataFrame:
    source = dataset_cfg.get("source", "local_db")
    if source == "local_db":
        if not database_url:
            raise ValueError("database_url is required for source=local_db")
        return load_from_local_db(dataset_cfg, database_url=database_url)
    if source == "external_csv":
        return load_from_external_csv(research_dir, dataset_cfg)
    if source == "external_api":
        return load_from_external_api(research_dir, dataset_cfg)
    raise ValueError(f"Unsupported dataset.source: {source}")
