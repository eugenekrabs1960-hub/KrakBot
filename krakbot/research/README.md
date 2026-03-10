# KrakBot Research Sidecar (Offline ML Baseline)

This folder is an **offline research sidecar** for SOL/USD model experiments using KrakBot's own stored market data.

## Safety / Governance Boundaries
- **Research outputs are advisory only.**
- **No direct execution from model outputs.**
- **All model-to-execution integration requires a separate reviewed phase.**

No live-trading architecture or execution path is modified by this sidecar.

## What this does
1. Exports SOL/USD candles (and optional market-trades aggregates) from Postgres.
2. Builds a simple explainable feature set:
   - returns (1, 5, 15 bars)
   - rolling volatility
   - momentum
   - RSI-like oscillator
   - volume change
3. Trains a baseline logistic regression model with a no-leakage time split.
4. Evaluates classification + trading-style proxy metrics and writes reports.

## Structure
- `configs/baseline.yaml` - data/model/split params
- `scripts/` - runnable pipeline entrypoints
- `src/` - reusable dataset/features/model/metrics/split code
- `data/` - local artifacts (gitignored)
- `reports/` - generated evaluation outputs (gitignored except `.gitkeep`)

## Setup
From `krakbot/research/`:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## One-command baseline run
Set DB URL, then run:

```bash
export DATABASE_URL='postgresql+psycopg://krakbot:krakbot@localhost:5432/krakbot'
./scripts/run_baseline.sh
```

Or pass a custom config path:

```bash
./scripts/run_baseline.sh configs/baseline.yaml
```

## Outputs
After success:
- `reports/metrics.json`
- `reports/summary.md`
- `reports/plots/equity_curve.png`
- `data/baseline_model.joblib`
- `data/training_metadata.json`
- `data/test_predictions.parquet`

## Notes
- Uses read-only SQL `SELECT` against existing `candles` and `market_trades` tables.
- Timestamps are normalized to UTC datetime (`ts`) and de-duplicated by bar timestamp.
- If DB has too little data, export step fails early via `min_rows` check.
