from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from app.api.models import runtime_settings
from app.core.database import SessionLocal
from app.services.decision_engine import run_decision_cycle
from app.services.ingest.hyperliquid_market import fetch_market_snapshot
from app.services.features.market_features import compute_market_features
from app.services.features.ml_scores import compute_ml_scores
from app.services.loops.metrics import start_loop_run, finish_loop_run

logger = logging.getLogger(__name__)


class LoopScheduler:
    def __init__(self) -> None:
        self._running = False
        self._feature_task: asyncio.Task | None = None
        self._decision_task: asyncio.Task | None = None
        self.last_feature_scores: dict = {}
        self.last_error: str | None = None
        self.last_feature_run_at: str | None = None
        self.last_decision_run_at: str | None = None

    async def start(self):
        if self._running:
            return
        self._running = True
        self._feature_task = asyncio.create_task(self._feature_loop())
        self._decision_task = asyncio.create_task(self._decision_loop())

    async def stop(self):
        self._running = False
        for t in [self._feature_task, self._decision_task]:
            if t:
                t.cancel()
        for t in [self._feature_task, self._decision_task]:
            if t:
                try:
                    await t
                except BaseException:
                    pass

    async def _feature_loop(self):
        while self._running:
            started = datetime.now(timezone.utc)
            try:
                with SessionLocal() as db:
                    run_id = start_loop_run(db, 'feature')
                    scores = {}
                    for coin in runtime_settings.universe.tracked_coins:
                        m = fetch_market_snapshot(coin)
                        f = compute_market_features(m)
                        s = compute_ml_scores(f)
                        scores[coin] = s
                    self.last_feature_scores = scores
                    self.last_feature_run_at = datetime.now(timezone.utc).isoformat()
                    finish_loop_run(db, run_id, 'ok', started)
            except Exception as e:
                self.last_error = f"feature_loop:{e}"
                logger.warning("feature loop error: %s", e)
                try:
                    with SessionLocal() as db:
                        run_id = start_loop_run(db, 'feature')
                        finish_loop_run(db, run_id, 'error', started, str(e))
                except Exception:
                    pass
            await asyncio.sleep(max(10, runtime_settings.loop.feature_refresh_seconds))

    async def _decision_loop(self):
        while self._running:
            started = datetime.now(timezone.utc)
            try:
                with SessionLocal() as db:
                    run_id = start_loop_run(db, 'decision')
                    run_decision_cycle(db)
                    self.last_decision_run_at = datetime.now(timezone.utc).isoformat()
                    finish_loop_run(db, run_id, 'ok', started)
            except Exception as e:
                self.last_error = f"decision_loop:{e}"
                logger.warning("decision loop error: %s", e)
                try:
                    with SessionLocal() as db:
                        run_id = start_loop_run(db, 'decision')
                        finish_loop_run(db, run_id, 'error', started, str(e))
                except Exception:
                    pass
            await asyncio.sleep(max(30, runtime_settings.loop.decision_cycle_seconds))


loop_scheduler = LoopScheduler()
