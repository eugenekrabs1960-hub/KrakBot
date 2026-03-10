#!/usr/bin/env bash
set -euo pipefail

API_BASE="${KRAKBOT_API_BASE:-http://localhost:8010/api}"
UI_BASE="${KRAKBOT_UI_BASE:-http://localhost:5173}"

json_get() {
  local url="$1"
  curl -fsS "$url"
}

json_post() {
  local url="$1"
  local body="$2"
  shift 2
  curl -fsS -X POST "$url" -H 'Content-Type: application/json' "$@" -d "$body"
}

echo "[smoke] health"
json_get "$API_BASE/health" >/dev/null

echo "[smoke] control stop->start"
json_post "$API_BASE/control/bot" '{"command":"stop"}' >/dev/null
json_post "$API_BASE/control/bot" '{"command":"start"}' >/dev/null
json_get "$API_BASE/control/bot" >/dev/null

echo "[smoke] create strategy instance"
SID=$(json_post "$API_BASE/strategies/instances" '{"strategy_name":"trend_following","market":"SOL/USD","instrument_type":"spot","starting_equity_usd":10000,"params":{"smoke":true}}' | python3 -c 'import json,sys; print(json.load(sys.stdin)["strategy_instance_id"])')

echo "[smoke] paper order + idempotency replay"
IDEMP_KEY="smoke-$(date +%s)"
ORDER_PAYLOAD=$(cat <<EOF
{"strategy_instance_id":"$SID","market":"SOL/USD","side":"buy","qty":0.1,"order_type":"limit","limit_price":123.45}
EOF
)
json_post "$API_BASE/trades/paper-order" "$ORDER_PAYLOAD" -H "x-idempotency-key: $IDEMP_KEY" >/dev/null
json_post "$API_BASE/trades/paper-order" "$ORDER_PAYLOAD" -H "x-idempotency-key: $IDEMP_KEY" >/dev/null

echo "[smoke] list pages"
json_get "$API_BASE/strategies" >/dev/null
json_get "$API_BASE/strategies/$SID" >/dev/null
json_get "$API_BASE/trades?limit=10" >/dev/null
curl -fsS "$UI_BASE" >/dev/null

echo "✅ KrakBot smoke test passed"
