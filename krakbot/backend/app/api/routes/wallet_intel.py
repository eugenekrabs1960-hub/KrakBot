from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.db.session import get_db
from app.schemas.wallet_intel import WalletPipelineRunRequest, WalletToggleExclusionRequest
from app.services.wallet_intel import WalletIntelService
from app.adapters.wallet_intel_providers import HeliusProvider, HeliusProviderStub

router = APIRouter(prefix='/wallet-intel', tags=['wallet-intel'])


@router.get('/health')
def wallet_intel_health(db: Session = Depends(get_db)):
    row = db.execute(
        text(
            """
            SELECT cohort_id, signal_ts, bias_state, benchmark_confidence, degraded_state
            FROM wallet_benchmark_signal
            ORDER BY signal_ts DESC
            LIMIT 1
            """
        )
    ).mappings().first()
    return {
        'ok': True,
        'latest_signal': dict(row) if row else None,
    }


@router.post('/admin/run-pipeline')
async def run_pipeline(payload: WalletPipelineRunRequest, db: Session = Depends(get_db)):
    svc = WalletIntelService()

    events = []
    if payload.provider == 'helius':
        # Try real provider first, fallback to stub if not configured.
        provider = HeliusProvider()
        fetched, _ = await provider.fetch_wallet_events(limit=100)
        if not fetched:
            provider = HeliusProviderStub()
            fetched, _ = await provider.fetch_wallet_events(limit=100)
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

    return svc.run_pipeline(db, provider_events=events)


@router.get('/cohorts/{cohort_id}/latest')
def cohort_latest(cohort_id: str, db: Session = Depends(get_db)):
    snapshot = db.execute(
        text(
            """
            SELECT id, cohort_id, cohort_version, as_of_ts, metrics_json, signal_state, confidence_score
            FROM wallet_cohort_snapshot
            WHERE cohort_id=:cohort_id
            ORDER BY as_of_ts DESC
            LIMIT 1
            """
        ),
        {'cohort_id': cohort_id},
    ).mappings().first()

    members = []
    if snapshot:
        members = db.execute(
            text(
                """
                SELECT wallet_id, rank, score_total, status
                FROM wallet_cohort_membership
                WHERE cohort_id=:cohort_id
                  AND cohort_version=:cohort_version
                ORDER BY rank ASC
                LIMIT 100
                """
            ),
            {
                'cohort_id': cohort_id,
                'cohort_version': snapshot['cohort_version'],
            },
        ).mappings().all()

    return {
        'snapshot': dict(snapshot) if snapshot else None,
        'members': [dict(m) for m in members],
    }


@router.post('/admin/toggle-exclusion')
def toggle_exclusion(payload: WalletToggleExclusionRequest, db: Session = Depends(get_db)):
    db.execute(
        text('UPDATE wallet_master SET manual_force_exclude=:force_exclude, updated_at=NOW() WHERE id=:wallet_id'),
        {'wallet_id': payload.wallet_id, 'force_exclude': payload.force_exclude},
    )
    db.commit()
    return {'ok': True, 'wallet_id': payload.wallet_id, 'force_exclude': payload.force_exclude}
