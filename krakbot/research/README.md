# KrakBot Research Sidecar (Offline ML Baseline)

This folder is an **offline research sidecar** for SOL/USD model experiments using KrakBot's own stored market data or external historical datasets.

## Safety / Governance Boundaries
- **Research outputs are advisory only.**
- **No direct execution from model outputs.**
- **All model-to-execution integration requires a separate reviewed phase.**

No live-trading architecture or execution path is modified by this sidecar.

## What this does
1. Loads candles from one of three sources (`dataset.source`):
   - `local_db` (Postgres candles + optional market trades)
   - `external_csv` (CSV OHLCV from `data/raw/`)
   - `external_api` (minimal Kraken OHLC pull)
2. Normalizes data to one canonical schema used by the same feature/training flow.
3. Runs data-quality checks (monotonic ts, dedupe, missing intervals, OHLC sanity).
4. Builds a simple explainable feature set.
5. Trains a baseline logistic regression model with a no-leakage time split.
6. Evaluates classification + trading-style proxy metrics and writes reports.

## Structure
- `configs/baseline.yaml` - default config and source selector
- `configs/external_csv_example.yaml` - CSV source example
- `configs/external_api_example.yaml` - Kraken API source example
- `scripts/` - runnable pipeline entrypoints
- `src/` - reusable dataset/features/model/metrics/split code
- `data/raw/` - raw external source files/API snapshots
- `data/` - normalized artifacts (gitignored)
- `reports/` - evaluation and data-quality outputs

## Setup
From `krakbot/research/`:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Exact run commands

### 1) local_db source

```bash
cd krakbot/research
export DATABASE_URL='postgresql+psycopg://krakbot:krakbot@localhost:5432/krakbot'
./scripts/run_baseline.sh configs/baseline.yaml
```

(`configs/baseline.yaml` defaults to `dataset.source: local_db`.)

### 2) external_csv source

Put CSV under `krakbot/research/data/raw/` and map columns in config (`timestamp/open/high/low/close/volume` mapping supported):

```bash
cd krakbot/research
cp configs/external_csv_example.yaml /tmp/external_csv_run.yaml
# edit /tmp/external_csv_run.yaml -> dataset.external_csv.path and column_mapping
./scripts/run_baseline.sh /tmp/external_csv_run.yaml
```

No DB URL needed for CSV mode.

### 3) external_api source (Kraken)

```bash
cd krakbot/research
./scripts/run_baseline.sh configs/external_api_example.yaml
```

Notes:
- Uses Kraken public OHLC endpoint (no credentials required).
- Pull is bounded by `dataset.external_api.limit` (1..720).
- Raw pull is saved under `data/raw/kraken_ohlc_*`.

## Labeling behavior (Baseline v2)
- `features.label_horizon` supports `1`, `3`, or `5` bars (configurable).
- `future_return = close[t+h] / close[t] - 1`.
- `features.label_neutral_band_bps` defines a no-trade band around zero return.
  - Positive class (`target=1`): `future_return > +band`
  - Negative class (`target=0`): `future_return < -band`
  - Neutral (`target_raw=0`): `-band <= future_return <= +band`
- `features.neutral_handling`:
  - `drop` (default for v2): neutral rows are filtered before training/eval.
  - `keep_as_negative`: neutral rows are retained and mapped to class `0`.

This keeps the model path deterministic and binary while still allowing neutral-band filtering.

## Baseline v2 run commands

```bash
cd krakbot/research
export DATABASE_URL='postgresql+psycopg://krakbot:krakbot@localhost:5432/krakbot'
./scripts/run_baseline.sh configs/baseline_v2_5k.yaml
./scripts/run_baseline.sh configs/baseline_v2_20k.yaml
```

## Outputs
After success:
- `reports/data_quality.json`
- `reports/data_quality.md`
- `reports/metrics.json`
- `reports/summary.md`
- `reports/plots/equity_curve.png`
- `data/baseline_model.joblib`
- `data/training_metadata.json`
- `data/test_predictions.parquet`

## Notes
- Existing downstream scripts (`build_features.py`, `train_baseline.py`, `evaluate.py`) still operate on the same canonical dataset artifact path.
- If exported data is too small, export fails via `dataset.min_rows` check.
