from __future__ import annotations

import asyncio
import logging

from app.core.config import settings
from app.core.database import SessionLocal
from app.services.autonomy.rollback_monitor import rollback_tick

logger = logging.getLogger(__name__)


class AutonomyRollbackWorker:
    def __init__(self):
        self._running = False
        self._task: asyncio.Task | None = None

    async def start(self):
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._run_loop(), name='autonomy-rollback-worker')

    async def stop(self):
        self._running = False
        t = self._task
        if t:
            t.cancel()
            try:
                await t
            except asyncio.CancelledError:
                pass
            self._task = None

    async def _run_loop(self):
        while self._running:
            try:
                with SessionLocal() as db:
                    out = rollback_tick(db)
                    db.commit()
                    if out.get('rolled_back') or out.get('blocked'):
                        logger.info('autonomy_rollback tick result=%s', out)
            except Exception as e:
                logger.exception('autonomy_rollback tick error: %s', e)
            await asyncio.sleep(max(10, int(settings.autonomy_rollback_interval_sec or 120)))


autonomy_rollback_worker = AutonomyRollbackWorker()
