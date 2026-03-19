from time import perf_counter

import requests
from fastapi import APIRouter

from app.core.config import settings

router = APIRouter(tags=['model-runtime'])


@router.get('/model/health')
def model_health():
    started = perf_counter()
    ok = False
    models = []
    err = None
    try:
        r = requests.get(f"{settings.local_model_base_url.rstrip('/')}/v1/models", timeout=min(settings.local_model_timeout_sec, 10))
        r.raise_for_status()
        body = r.json()
        models = [m.get('id') or m.get('name') for m in body.get('data', body.get('models', []))]
        ok = True
    except Exception as e:
        err = str(e)

    latency_ms = int((perf_counter() - started) * 1000)
    return {
        'ok': ok,
        'base_url': settings.local_model_base_url,
        'configured_model': settings.local_model_name,
        'reachable_models': models,
        'latency_ms': latency_ms,
        'error': err,
    }
