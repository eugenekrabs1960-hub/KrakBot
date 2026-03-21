#!/bin/sh
set -eu

TARGET_URL="${WATCHDOG_TARGET_URL:-http://backend:8010}"
BACKEND_CONTAINER="${WATCHDOG_BACKEND_CONTAINER:-deploy-backend-1}"
INTERVAL_SEC="${WATCHDOG_INTERVAL_SEC:-20}"
FAILS_BEFORE_RESTART="${WATCHDOG_FAILS_BEFORE_RESTART:-2}"
COOLDOWN_SEC="${WATCHDOG_RESTART_COOLDOWN_SEC:-20}"

fail_count=0

while true; do
  health_json="$(curl -fsS --max-time 5 "$TARGET_URL/api/model/health" 2>/dev/null || true)"
  loops_json="$(curl -fsS --max-time 5 "$TARGET_URL/api/loops/status" 2>/dev/null || true)"

  model_ok=false
  loop_running=false

  if echo "$health_json" | grep -Eq '"ok"[[:space:]]*:[[:space:]]*true'; then
    model_ok=true
  fi

  if echo "$loops_json" | grep -Eq '"running"[[:space:]]*:[[:space:]]*true'; then
    loop_running=true
  fi

  if [ "$model_ok" = false ] && [ "$loop_running" = false ]; then
    fail_count=$((fail_count + 1))
  else
    fail_count=0
  fi

  if [ "$fail_count" -ge "$FAILS_BEFORE_RESTART" ]; then
    echo "[watchdog] triggering backend restart: model_ok=$model_ok loop_running=$loop_running fails=$fail_count" >&2
    docker restart "$BACKEND_CONTAINER" >/dev/null 2>&1 || true
    fail_count=0
    sleep "$COOLDOWN_SEC"
  fi

  sleep "$INTERVAL_SEC"
done
