from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from contextlib import suppress
from typing import Awaitable, Callable

from sqlalchemy import text

from app.adapters.wallet_intel_providers import HeliusProvider, HeliusProviderStub
from app.core.config import settings
from app.db.session import SessionLocal
from app.services.wallet_intel import WalletIntelService
from app.services.checkpoints import load_checkpoint, save_checkpoint

logger = logging.getLogger(__name__)


class WalletIntelSchedulerService:
    def __init__(self):
        self._task: asyncio.Task | None = None
        self._running = False

    async def start(self):
        if self._running or not settings.wallet_intel_scheduler_enabled:
            return
        self._running = True
        self._task = asyncio.create_task(self._run_loop(), name='wallet-intel-scheduler')
        logger.info('wallet_intel_scheduler enabled interval=%ss lock_ttl=%ss',
                    settings.wallet_intel_scheduler_interval_sec,
                    settings.wallet_intel_scheduler_lock_ttl_sec)

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            with suppress(asyncio.CancelledError):
                await self._task

    async def _run_loop(self):
        while self._running:
            try:
                out = await self.run_once(source='scheduler')
                if not out.get('ok'):
                    logger.info('wallet_intel_scheduler tick skipped: %s', out)
                else:
                    logger.info('wallet_intel_scheduler tick complete: run_id=%s status=%s', out.get('run_id'), out.get('status'))
            except Exception as exc:
                logger.exception('wallet_intel_scheduler loop error: %s', exc)
            await asyncio.sleep(max(15, int(settings.wallet_intel_scheduler_interval_sec)))

    async def _fetch_provider_events(self, *, cursor: str | None = None):
        provider = HeliusProvider()
        fetched, next_cursor = await provider.fetch_wallet_events(cursor=cursor, limit=200)
        if not fetched:
            provider = HeliusProviderStub()
            fetched, next_cursor = await provider.fetch_wallet_events(cursor=cursor, limit=200)
        events = [
            {
                'provider': x.provider,
                'chain': x.chain,
                'provider_event_id': x.provider_event_id,
                'wallet_address': x.wallet_address,
                'event_ts': x.event_ts,
                'payload': x.payload,
            }
            for x in fetched
        ]
        return events, next_cursor

    def _acquire_lock(self, db, run_id: str, now_ms: int) -> bool:
        ttl_ms = max(60, int(settings.wallet_intel_scheduler_lock_ttl_sec)) * 1000
        expired_before = now_ms - ttl_ms
        db.execute(
            text(
                """
                INSERT INTO wallet_pipeline_lock(lock_name, owner_run_id, acquired_at_ms, heartbeat_at_ms)
                VALUES ('wallet_pipeline', NULL, NULL, NULL)
                ON CONFLICT (lock_name) DO NOTHING
                """
            )
        )
        result = db.execute(
            text(
                """
                UPDATE wallet_pipeline_lock
                SET owner_run_id=:run_id,
                    acquired_at_ms=:now_ms,
                    heartbeat_at_ms=:now_ms,
                    updated_at=CURRENT_TIMESTAMP
                WHERE lock_name='wallet_pipeline'
                  AND (owner_run_id IS NULL OR heartbeat_at_ms IS NULL OR heartbeat_at_ms < :expired_before)
                """
            ),
            {'run_id': run_id, 'now_ms': now_ms, 'expired_before': expired_before},
        )
        return result.rowcount == 1

    def _heartbeat(self, db, run_id: str, now_ms: int):
        db.execute(
            text(
                """
                UPDATE wallet_pipeline_lock
                SET heartbeat_at_ms=:now_ms, updated_at=CURRENT_TIMESTAMP
                WHERE lock_name='wallet_pipeline' AND owner_run_id=:run_id
                """
            ),
            {'now_ms': now_ms, 'run_id': run_id},
        )

    def _release_lock(self, db, run_id: str):
        db.execute(
            text(
                """
                UPDATE wallet_pipeline_lock
                SET owner_run_id=NULL, acquired_at_ms=NULL, heartbeat_at_ms=NULL, updated_at=CURRENT_TIMESTAMP
                WHERE lock_name='wallet_pipeline' AND owner_run_id=:run_id
                """
            ),
            {'run_id': run_id},
        )

    async def run_once(self, source: str = 'manual'):
        run_id = f"wsched_{uuid.uuid4().hex[:10]}"
        started_at_ms = int(time.time() * 1000)

        db = SessionLocal()
        try:
            got_lock = self._acquire_lock(db, run_id=run_id, now_ms=started_at_ms)
            if not got_lock:
                db.rollback()
                return {'ok': False, 'status': 'skipped', 'reason': 'lock_held'}

            db.execute(
                text(
                    """
                    INSERT INTO wallet_pipeline_run_ledger(run_id, source, status, started_at_ms, heartbeat_at_ms)
                    VALUES (:run_id, :source, 'running', :started_at_ms, :started_at_ms)
                    """
                ),
                {'run_id': run_id, 'source': source, 'started_at_ms': started_at_ms},
            )
            db.commit()

            checkpoint = load_checkpoint(db, 'wallet_intel_helius_cursor') or {}
            current_cursor = checkpoint.get('cursor') if isinstance(checkpoint, dict) else None
            events, next_cursor = await self._fetch_provider_events(cursor=current_cursor)

            self._heartbeat(db, run_id=run_id, now_ms=int(time.time() * 1000))
            db.commit()

            pipeline_result = WalletIntelService().run_pipeline(db, provider_events=events)
            pipeline_result['fetch_cursor_before'] = current_cursor
            pipeline_result['fetch_cursor_after'] = next_cursor
            pipeline_result['fetched_events'] = len(events)
            finished_ms = int(time.time() * 1000)
            if next_cursor:
                save_checkpoint(db, 'wallet_intel_helius_cursor', {
                    'cursor': next_cursor,
                    'updated_at_ms': finished_ms,
                    'last_run_id': run_id,
                })

            db.execute(
                text(
                    """
                    UPDATE wallet_pipeline_run_ledger
                    SET status='success',
                        heartbeat_at_ms=:finished_ms,
                        finished_at_ms=:finished_ms,
                        duration_ms=:duration_ms,
                        result_json=CAST(:result_json AS jsonb)
                    WHERE run_id=:run_id
                    """
                ),
                {
                    'run_id': run_id,
                    'finished_ms': finished_ms,
                    'duration_ms': finished_ms - started_at_ms,
                    'result_json': json.dumps(pipeline_result),
                },
            )
            self._release_lock(db, run_id)
            db.commit()
            return {'ok': True, 'status': 'success', 'run_id': run_id, 'result': pipeline_result}
        except Exception as exc:
            finished_ms = int(time.time() * 1000)
            try:
                db.execute(
                    text(
                        """
                        UPDATE wallet_pipeline_run_ledger
                        SET status='failed',
                            heartbeat_at_ms=:finished_ms,
                            finished_at_ms=:finished_ms,
                            duration_ms=:duration_ms,
                            error_text=:error_text
                        WHERE run_id=:run_id
                        """
                    ),
                    {
                        'run_id': run_id,
                        'finished_ms': finished_ms,
                        'duration_ms': finished_ms - started_at_ms,
                        'error_text': str(exc)[:2000],
                    },
                )
                self._release_lock(db, run_id)
                db.commit()
            except Exception:
                db.rollback()
            logger.exception('wallet_intel_scheduler run failed run_id=%s', run_id)
            return {'ok': False, 'status': 'failed', 'run_id': run_id, 'error': str(exc)}
        finally:
            db.close()


wallet_intel_scheduler = WalletIntelSchedulerService()
