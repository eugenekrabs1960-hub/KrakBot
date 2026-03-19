from time import perf_counter

import requests
from fastapi import APIRouter

from app.core.config import settings
from app.services.models.qwen_local_adapter import QwenLocalAdapter

router = APIRouter(tags=['model-runtime'])


@router.get('/model/health')
def model_health():
    started = perf_counter()
    ok = False
    models = []
    err = None
    completion_ok = False

    headers = {}
    if settings.local_model_api_key:
        headers['Authorization'] = f"Bearer {settings.local_model_api_key}"

    try:
        r = requests.get(f"{settings.local_model_base_url.rstrip('/')}/v1/models", headers=headers, timeout=min(settings.local_model_timeout_sec, 10))
        r.raise_for_status()
        body = r.json()
        models = [m.get('id') or m.get('name') or m.get('model') for m in body.get('data', body.get('models', []))]

        # completion-path probe so health reflects actual analyst dispatch viability
        payload = {
            "model": settings.local_model_name,
            "messages": [
                {"role": "system", "content": "Return JSON only: {\"ok\":true}"},
                {"role": "user", "content": "ping"},
            ],
            "temperature": 0,
            "max_tokens": 40,
        }
        cr = requests.post(
            f"{settings.local_model_base_url.rstrip('/')}/v1/chat/completions",
            headers={"content-type": "application/json", **headers},
            json=payload,
            timeout=min(settings.local_model_timeout_sec, 10),
        )
        if cr.status_code == 200:
            completion_ok = True
        else:
            err = f"chat_probe_status_{cr.status_code}"

        ok = completion_ok
    except Exception as e:
        err = str(e)

    latency_ms = int((perf_counter() - started) * 1000)
    return {
        'ok': ok,
        'base_url': settings.local_model_base_url,
        'configured_model': settings.local_model_name,
        'api_key_configured': bool(settings.local_model_api_key),
        'reachable_models': models,
        'completion_probe_ok': completion_ok,
        'latency_ms': latency_ms,
        'error': err,
    }


@router.get('/model/runtime-metrics')
def model_runtime_metrics():
    return QwenLocalAdapter.metrics_snapshot()
