from __future__ import annotations

import asyncio
import logging
from contextlib import suppress

from app.core.config import settings
from app.db.session import SessionLocal
from app.services.jason_agent import run_jason_once, run_jason_rule_based_once

logger = logging.getLogger(__name__)


class JasonLoopService:
    def __init__(self):
        self._task: asyncio.Task | None = None
        self._running = False

    async def start(self):
        if self._running or not settings.jason_loop_enabled:
            return
        self._running = True
        self._task = asyncio.create_task(self._run_loop(), name='jason-loop')
        logger.info('jason_loop enabled interval=%ss', settings.jason_loop_interval_sec)

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            with suppress(asyncio.CancelledError):
                await self._task

    async def _run_loop(self):
        while self._running:
            db = SessionLocal()
            try:
                out = run_jason_once(db)
                if not out.get('ok') and 'OPENAI_API_KEY missing' in str(out.get('error', '')):
                    out = run_jason_rule_based_once(db)
                if not out.get('ok'):
                    logger.info('jason_loop tick skipped: %s', out)
                else:
                    d = out.get('decision') or {}
                    logger.info('jason_loop tick ok action=%s symbol=%s', d.get('action'), d.get('symbol'))
            except Exception as exc:
                logger.exception('jason_loop error: %s', exc)
            finally:
                db.close()
            await asyncio.sleep(max(5, int(settings.jason_loop_interval_sec)))


jason_loop = JasonLoopService()
