from __future__ import annotations

import asyncio
import logging

from app.core.config import settings
from app.core.database import SessionLocal
from app.services.autonomy.auto_apply import auto_apply_tick

logger = logging.getLogger(__name__)


class AutonomyAutoApplyWorker:
    def __init__(self):
        self._running = False
        self._task: asyncio.Task | None = None

    async def start(self):
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._run_loop(), name='autonomy-auto-apply-worker')

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
                    out = auto_apply_tick(db)
                    db.commit()
                    if out.get('applied') or out.get('blocked'):
                        logger.info('autonomy_auto_apply tick result=%s', out)
            except Exception as e:
                logger.exception('autonomy_auto_apply tick error: %s', e)
            await asyncio.sleep(max(5, int(settings.autonomy_auto_apply_interval_sec or 60)))


autonomy_auto_apply_worker = AutonomyAutoApplyWorker()
