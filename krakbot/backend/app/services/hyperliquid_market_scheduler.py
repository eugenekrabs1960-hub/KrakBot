from __future__ import annotations

import asyncio
import logging
from contextlib import suppress

from app.core.config import settings
from app.db.session import SessionLocal
from app.services.checkpoints import save_checkpoint
from app.services.hyperliquid_market_data import HyperliquidMarketDataService

logger = logging.getLogger(__name__)


class HyperliquidMarketScheduler:
    def __init__(self):
        self._task: asyncio.Task | None = None
        self._running = False

    async def start(self):
        if self._running or not settings.hyperliquid_market_collector_enabled:
            return
        self._running = True
        self._task = asyncio.create_task(self._run_loop(), name='hyperliquid-market-scheduler')
        logger.info('hyperliquid market scheduler enabled interval=%ss', settings.hyperliquid_market_collector_interval_sec)

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            with suppress(asyncio.CancelledError):
                await self._task

    async def _run_loop(self):
        while self._running:
            try:
                self.run_once()
            except Exception as exc:
                logger.exception('hyperliquid market scheduler tick error: %s', exc)
            await asyncio.sleep(max(5, int(settings.hyperliquid_market_collector_interval_sec)))

    def run_once(self):
        db = SessionLocal()
        try:
            svc = HyperliquidMarketDataService(environment=settings.hyperliquid_environment)
            out = svc.collect_once(db, symbols_limit=settings.hyperliquid_market_collector_symbols_limit)
            save_checkpoint(db, 'hyperliquid_market_collector', out.__dict__)
            return out.__dict__
        except Exception as exc:
            return {'ok': False, 'error': str(exc)[:300]}
        finally:
            db.close()


hyperliquid_market_scheduler = HyperliquidMarketScheduler()
