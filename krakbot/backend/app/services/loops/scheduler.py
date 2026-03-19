from __future__ import annotations

import asyncio
import logging

from app.api.models import runtime_settings
from app.core.database import SessionLocal
from app.services.decision_engine import run_decision_cycle
from app.services.ingest.hyperliquid_market import fetch_market_snapshot
from app.services.features.market_features import compute_market_features
from app.services.features.ml_scores import compute_ml_scores

logger = logging.getLogger(__name__)


class LoopScheduler:
    def __init__(self) -> None:
        self._running = False
        self._feature_task: asyncio.Task | None = None
        self._decision_task: asyncio.Task | None = None
        self.last_feature_scores: dict = {}

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
                except Exception:
                    pass

    async def _feature_loop(self):
        while self._running:
            try:
                scores = {}
                for coin in runtime_settings.universe.tracked_coins:
                    m = fetch_market_snapshot(coin)
                    f = compute_market_features(m)
                    s = compute_ml_scores(f)
                    scores[coin] = s
                self.last_feature_scores = scores
            except Exception as e:
                logger.warning("feature loop error: %s", e)
            await asyncio.sleep(max(10, runtime_settings.loop.feature_refresh_seconds))

    async def _decision_loop(self):
        while self._running:
            try:
                with SessionLocal() as db:
                    run_decision_cycle(db)
            except Exception as e:
                logger.warning("decision loop error: %s", e)
            await asyncio.sleep(max(30, runtime_settings.loop.decision_cycle_seconds))


loop_scheduler = LoopScheduler()
