#!/usr/bin/env bash
set -euo pipefail

RESEARCH_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG_PATH="${1:-configs/baseline.yaml}"
DB_URL="${DATABASE_URL:-${KRAKBOT_DATABASE_URL:-}}"

if [[ -z "${DB_URL}" ]]; then
  echo "ERROR: Set DATABASE_URL (or KRAKBOT_DATABASE_URL) before running." >&2
  exit 1
fi

cd "${RESEARCH_DIR}"

python3 scripts/export_dataset.py --config "${CONFIG_PATH}" --database-url "${DB_URL}"
python3 scripts/build_features.py --config "${CONFIG_PATH}"
python3 scripts/train_baseline.py --config "${CONFIG_PATH}"
python3 scripts/evaluate.py --config "${CONFIG_PATH}"

echo "Baseline pipeline complete. See ${RESEARCH_DIR}/reports/"
