from fastapi import APIRouter

from app.services.loops.scheduler import loop_scheduler

router = APIRouter(tags=["loops"])


@router.get('/loops/status')
def loops_status():
    return {
        "running": True,
        "tracked_scores": list(loop_scheduler.last_feature_scores.keys()),
        "feature_count": len(loop_scheduler.last_feature_scores),
    }
