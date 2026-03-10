#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

import pandas as pd


def _get_json(url: str) -> dict:
    with urlopen(url, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_kraken_solusd_1m(max_pages: int = 250, sleep_s: float = 0.15) -> pd.DataFrame:
    pair = "SOLUSD"
    interval = 1
    since = 0
    all_rows: list[list] = []
    seen_ts: set[int] = set()

    for _ in range(max_pages):
        url = f"https://api.kraken.com/0/public/OHLC?{urlencode({'pair': pair, 'interval': interval, 'since': since})}"
        payload = _get_json(url)
        if payload.get("error"):
            raise RuntimeError(f"Kraken API error: {payload['error']}")

        result = payload.get("result", {})
        rows = result.get(pair) or next((v for k, v in result.items() if k != "last"), [])
        if not rows:
            break

        inserted = 0
        for r in rows:
            ts = int(float(r[0]))
            if ts not in seen_ts:
                seen_ts.add(ts)
                all_rows.append(r)
                inserted += 1

        last = int(result.get("last", since))
        if inserted == 0 or last <= since:
            break
        since = last
        time.sleep(sleep_s)

    cols = ["open_time", "open", "high", "low", "close", "vwap", "volume", "count"]
    raw = pd.DataFrame(all_rows, columns=cols)
    raw["open_time"] = pd.to_numeric(raw["open_time"], errors="coerce").astype("Int64")
    raw = raw.dropna(subset=["open_time"]).astype({"open_time": "int64"}).sort_values("open_time")

    return pd.DataFrame(
        {
            "timestamp": pd.to_datetime(raw["open_time"], unit="s", utc=True).dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "open": pd.to_numeric(raw["open"], errors="coerce"),
            "high": pd.to_numeric(raw["high"], errors="coerce"),
            "low": pd.to_numeric(raw["low"], errors="coerce"),
            "close": pd.to_numeric(raw["close"], errors="coerce"),
            "volume": pd.to_numeric(raw["volume"], errors="coerce"),
        }
    ).dropna()


def fetch_binance_solusdt_1m(max_pages: int = 300, sleep_s: float = 0.1) -> pd.DataFrame:
    symbol = "SOLUSDT"
    interval = "1m"
    limit = 1000
    start_ms = 1596240000000  # 2020-08-01
    now_ms = int(time.time() * 1000)

    out_rows: list[list] = []
    page = 0
    while page < max_pages and start_ms < now_ms:
        url = "https://api.binance.com/api/v3/klines?" + urlencode(
            {
                "symbol": symbol,
                "interval": interval,
                "limit": limit,
                "startTime": start_ms,
            }
        )
        rows = _get_json(url)
        if not isinstance(rows, list) or not rows:
            break

        out_rows.extend(rows)
        last_open = int(rows[-1][0])
        next_start = last_open + 60_000
        if next_start <= start_ms:
            break

        start_ms = next_start
        page += 1
        time.sleep(sleep_s)

    df = pd.DataFrame(out_rows)
    # [ open_time, open, high, low, close, volume, close_time, quote_volume, n_trades, ... ]
    return pd.DataFrame(
        {
            "timestamp": pd.to_datetime(pd.to_numeric(df[0], errors="coerce"), unit="ms", utc=True).dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "open": pd.to_numeric(df[1], errors="coerce"),
            "high": pd.to_numeric(df[2], errors="coerce"),
            "low": pd.to_numeric(df[3], errors="coerce"),
            "close": pd.to_numeric(df[4], errors="coerce"),
            "volume": pd.to_numeric(df[5], errors="coerce"),
        }
    ).dropna()


def write_csv(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, quoting=csv.QUOTE_MINIMAL)


def write_metadata(path: Path, *, venue: str, symbol: str, timeframe: str, rows: int, source_note: str) -> None:
    payload = {
        "download_time_utc": datetime.now(timezone.utc).isoformat(),
        "venue": venue,
        "symbol": symbol,
        "timeframe": timeframe,
        "row_count": int(rows),
        "source_note": source_note,
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run_export_and_capture_quality(research_dir: Path, config_rel: str, quality_prefix: str) -> None:
    import subprocess

    subprocess.run(["python3", "scripts/export_dataset.py", "--config", config_rel], cwd=research_dir, check=True)

    reports_dir = research_dir / "reports"
    src_json = reports_dir / "data_quality.json"
    src_md = reports_dir / "data_quality.md"
    if src_json.exists():
        shutil.copy2(src_json, reports_dir / f"data_quality_{quality_prefix}.json")
    if src_md.exists():
        shutil.copy2(src_md, reports_dir / f"data_quality_{quality_prefix}.md")


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch real Kraken + Binance proxy datasets for research")
    parser.add_argument("--kraken-pages", type=int, default=250)
    parser.add_argument("--binance-pages", type=int, default=300)
    args = parser.parse_args()

    research_dir = Path(__file__).resolve().parents[1]
    raw_dir = research_dir / "data" / "raw"

    kraken_df = fetch_kraken_solusd_1m(max_pages=args.kraken_pages)
    kraken_raw = raw_dir / "kraken_solusd_1m_history.csv"
    write_csv(kraken_df, kraken_raw)
    write_metadata(
        raw_dir / "kraken_solusd_1m_history.metadata.json",
        venue="Kraken",
        symbol="SOL/USD",
        timeframe="1m",
        rows=len(kraken_df),
        source_note="Primary venue; public Kraken OHLC endpoint with bounded paging.",
    )

    secondary_df = fetch_binance_solusdt_1m(max_pages=args.binance_pages)
    secondary_raw = raw_dir / "binance_solusdt_1m_proxy_history.csv"
    write_csv(secondary_df, secondary_raw)
    write_metadata(
        raw_dir / "binance_solusdt_1m_proxy_history.metadata.json",
        venue="Binance",
        symbol="SOLUSDT",
        timeframe="1m",
        rows=len(secondary_df),
        source_note="Secondary cross-venue proxy; not Kraken-native market microstructure.",
    )

    run_export_and_capture_quality(research_dir, "configs/real_kraken_history.yaml", "real_kraken_history")
    run_export_and_capture_quality(research_dir, "configs/real_secondary_history.yaml", "real_secondary_history")

    print(f"Saved: {kraken_raw} ({len(kraken_df)} rows)")
    print(f"Saved: {secondary_raw} ({len(secondary_df)} rows)")
    print("Quality reports:")
    print("- reports/data_quality_real_kraken_history.json|md")
    print("- reports/data_quality_real_secondary_history.json|md")


if __name__ == "__main__":
    main()
