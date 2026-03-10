import asyncio
import logging
import time
from collections import defaultdict, deque
from contextlib import suppress

from sqlalchemy import text

from app.adapters.execution.base import OrderIntent
from app.adapters.execution.freqtrade_adapter import FreqtradeExecutionAdapter
from app.core.config import settings
from app.db.session import SessionLocal
from app.services.orchestrator import OrchestratorService
from app.services.ws_hub import ws_hub

logger = logging.getLogger(__name__)


class LivePaperTestModeService:
    """
    Optional loop for continuous, bounded paper-order activity to aid UI verification.
    Strategy-scoped and gated by bot control state.
    """

    def __init__(self):
        self._task: asyncio.Task | None = None
        self._running = False
        self._attempt_history: dict[str, deque[float]] = defaultdict(deque)

    async def start(self):
        if self._running or not settings.live_paper_test_mode_enabled:
            return
        self._running = True
        self._task = asyncio.create_task(self._run_loop(), name='live-paper-test-mode')
        logger.info('live_paper_test_mode enabled: market=%s interval=%.2fs qty=%.6f max_per_min=%d',
                    settings.live_paper_test_market,
                    settings.live_paper_test_loop_interval_sec,
                    settings.live_paper_test_order_qty,
                    settings.live_paper_test_max_orders_per_minute)

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            with suppress(asyncio.CancelledError):
                await self._task

    async def _run_loop(self):
        while self._running:
            try:
                await self.run_once()
            except Exception as exc:
                logger.exception('live_paper_test_mode loop error: %s', exc)
            await asyncio.sleep(max(0.2, settings.live_paper_test_loop_interval_sec))

    async def run_once(self):
        db = SessionLocal()
        try:
            bot_state = OrchestratorService().get_state(db)
            candidates = self._load_candidates(db)

            for c in candidates:
                strategy_id = c['strategy_instance_id']
                now = time.time()

                decision = self._decide(c)
                can_attempt, reason = self._allow_attempt(strategy_id, now)

                decision_event = {
                    'type': 'paper_test.decision',
                    'ts': int(now * 1000),
                    'strategy_instance_id': strategy_id,
                    'market': c['market'],
                    'bot_state': bot_state,
                    'decision': decision,
                    'allowed': can_attempt,
                    'reason': reason,
                }
                logger.info('paper_test decision strategy=%s state=%s decision=%s allowed=%s reason=%s',
                            strategy_id, bot_state, decision, can_attempt, reason)
                await ws_hub.broadcast(decision_event)

                if bot_state != 'running' or decision == 'hold' or not can_attempt:
                    continue

                side = 'buy' if decision == 'enter' else 'sell'
                qty = max(0.0, settings.live_paper_test_order_qty)
                if qty <= 0:
                    continue

                adapter = FreqtradeExecutionAdapter(db)
                if settings.live_paper_test_force_paper_only:
                    adapter.bridge.enabled = False
                    adapter.bridge.base_url = ''

                self._attempt_history[strategy_id].append(now)
                result = adapter.submit_order(
                    OrderIntent(
                        strategy_instance_id=strategy_id,
                        market=c['market'],
                        side=side,
                        qty=qty,
                        order_type='market',
                        limit_price=None,
                    )
                )

                order_event = {
                    'type': 'paper_test.order_attempt',
                    'ts': int(time.time() * 1000),
                    'strategy_instance_id': strategy_id,
                    'market': c['market'],
                    'side': side,
                    'qty': qty,
                    'result': result,
                }
                logger.info('paper_test order_attempt strategy=%s side=%s qty=%.6f accepted=%s error=%s',
                            strategy_id, side, qty, result.get('accepted'), result.get('error_code'))
                await ws_hub.broadcast(order_event)
        finally:
            db.close()

    def _load_candidates(self, db) -> list[dict]:
        rows = db.execute(
            text(
                """
                SELECT si.id AS strategy_instance_id,
                       si.market,
                       COALESCE(pos.qty, 0) AS current_position_qty
                FROM strategy_instances si
                LEFT JOIN positions pos ON pos.strategy_instance_id = si.id AND pos.market = si.market
                WHERE si.enabled = TRUE
                  AND si.market = :market
                ORDER BY si.created_at ASC
                """
            ),
            {'market': settings.live_paper_test_market},
        ).mappings().all()
        return [dict(r) for r in rows]

    def _decide(self, candidate: dict) -> str:
        qty = float(candidate.get('current_position_qty') or 0.0)
        if qty > 0:
            return 'exit'
        return 'enter'

    def _allow_attempt(self, strategy_instance_id: str, now_s: float) -> tuple[bool, str]:
        history = self._attempt_history[strategy_instance_id]
        while history and now_s - history[0] > 60:
            history.popleft()

        if history and (now_s - history[-1]) < settings.live_paper_test_min_seconds_between_orders:
            return False, 'min_interval_guard'

        if len(history) >= settings.live_paper_test_max_orders_per_minute:
            return False, 'per_minute_rate_limit'

        return True, 'ok'


live_paper_test_mode = LivePaperTestModeService()
