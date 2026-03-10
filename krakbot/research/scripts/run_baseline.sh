#!/usr/bin/env bash
set -euo pipefail

RESEARCH_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG_PATH="${1:-configs/baseline.yaml}"
DB_URL="${DATABASE_URL:-${KRAKBOT_DATABASE_URL:-}}"

cd "${RESEARCH_DIR}"

SOURCE="$(python3 - <<'PY' "${CONFIG_PATH}"
import sys, yaml
with open(sys.argv[1], 'r', encoding='utf-8') as f:
    cfg = yaml.safe_load(f)
print(cfg.get('dataset', {}).get('source', 'local_db'))
PY
)"

if [[ "${SOURCE}" == "local_db" ]]; then
  if [[ -z "${DB_URL}" ]]; then
    echo "ERROR: Set DATABASE_URL (or KRAKBOT_DATABASE_URL) when dataset.source=local_db." >&2
    exit 1
  fi
  python3 scripts/export_dataset.py --config "${CONFIG_PATH}" --database-url "${DB_URL}"
else
  python3 scripts/export_dataset.py --config "${CONFIG_PATH}"
fi

python3 scripts/build_features.py --config "${CONFIG_PATH}"
python3 scripts/train_baseline.py --config "${CONFIG_PATH}"
python3 scripts/evaluate.py --config "${CONFIG_PATH}"

METRICS_PATH="$(python3 - <<'PY' "${CONFIG_PATH}"
import sys, yaml
with open(sys.argv[1], 'r', encoding='utf-8') as f:
    cfg = yaml.safe_load(f)
reports_dir = cfg.get('artifacts', {}).get('reports_dir', 'reports')
print(f"{reports_dir}/metrics.json")
PY
)"

GATE_CONFIG_PATH="${GATE_CONFIG_PATH:-configs/eval_gate.yaml}"
GATE_REPORT_PATH="$(python3 - <<'PY' "${CONFIG_PATH}"
import sys, yaml
with open(sys.argv[1], 'r', encoding='utf-8') as f:
    cfg = yaml.safe_load(f)
reports_dir = cfg.get('artifacts', {}).get('reports_dir', 'reports')
print(f"{reports_dir}/gate_verdict.md")
PY
)"
GATE_JSON_PATH="$(python3 - <<'PY' "${CONFIG_PATH}"
import sys, yaml
with open(sys.argv[1], 'r', encoding='utf-8') as f:
    cfg = yaml.safe_load(f)
reports_dir = cfg.get('artifacts', {}).get('reports_dir', 'reports')
print(f"{reports_dir}/gate_verdict.json")
PY
)"

python3 scripts/eval_gate.py \
  --metrics "${METRICS_PATH}" \
  --gate-config "${GATE_CONFIG_PATH}" \
  --report "${GATE_REPORT_PATH}" \
  --json-out "${GATE_JSON_PATH}"

echo "Baseline pipeline complete. Metrics: ${METRICS_PATH} | Gate: ${GATE_REPORT_PATH}"
