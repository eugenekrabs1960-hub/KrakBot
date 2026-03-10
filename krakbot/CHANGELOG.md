# CHANGELOG

## 2026-03 Stabilization Hotfixes

- Added backend API integration tests covering:
  - control state transitions
  - idempotent paper-order replay behavior
  - strategy list/detail correctness after fills
  - trade history consistency checks
- Added `scripts/smoke_local_stack.sh` for one-command post-`docker compose up` validation.
- Removed deprecated `version` field from `deploy/docker-compose.yml` to silence compose warnings.
- Updated frontend Controls, Strategy Comparison, and Trade History pages to poll backend state and display live API data.
- Added README verification runbook with exact `curl` checks and expected response shapes.
- Added idempotency payload-conflict handling (`409`) on `/api/trades/paper-order`.
- Enforced strict paper fill pricing from latest `market_trades.price` only; if unavailable, paper order is rejected with `no_market_trade_price` and no execution/portfolio mutation.
- Idempotent replay now returns the exact stored response body for both success and failure results.
