#!/usr/bin/env bash
set -euo pipefail

RESEARCH_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${RESEARCH_DIR}"

KRAKEN_PAGES="${KRAKEN_PAGES:-250}"
BINANCE_PAGES="${BINANCE_PAGES:-300}"

python3 scripts/fetch_real_datasets.py --kraken-pages "${KRAKEN_PAGES}" --binance-pages "${BINANCE_PAGES}"

echo "Real dataset fetch complete."
