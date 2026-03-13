from __future__ import annotations

import json
import time
from typing import Any

import requests
from sqlalchemy import text
from sqlalchemy.orm import Session

MODEL_REGISTRY_KEY = 'model_registry_v1'


def _dialect_name(db: Session) -> str:
    dialect = getattr(getattr(db, 'bind', None), 'dialect', None)
    return getattr(dialect, 'name', '')


def _default_registry() -> dict[str, Any]:
    return {
        'version': 1,
        'models': [
            {
                'id': 'gpt-5.4',
                'display_name': 'GPT-5.4',
                'provider_type': 'openai_hosted',
                'local': False,
                'paper_only': False,
                'supports': ['text', 'image'],
                'reasoning': True,
                'context_window': 266000,
                'max_tokens': 4000,
                'status': 'ready',
                'role': 'primary',
            },
            {
                'id': 'qwen3.5-9b-local',
                'display_name': 'Qwen3.5-9B-Q4_K_M (local)',
                'provider_type': 'openai_compatible',
                'base_url': 'http://10.50.0.30:8000/v1',
                'api_mode': 'openai-completions',
                'remote_model_id': 'Qwen3.5-9B-Q4_K_M.gguf',
                'local': True,
                'paper_only': True,
                'supports': ['text', 'image'],
                'reasoning': False,
                'context_window': 65536,
                'max_tokens': 2000,
                'status': 'ready',
                'role': 'challenger',
                'cost': 'local_zero',
                'auth_mode': 'none',
                'api_key_env': '',
                'context_tiers': {
                    'fast_decision': 8000,
                    'enhanced_decision': 12000,
                    'analysis_review': 16000,
                },
            },
        ],
    }


def _load_registry(db: Session) -> dict[str, Any]:
    row = db.execute(text('SELECT value FROM system_state WHERE key=:k LIMIT 1'), {'k': MODEL_REGISTRY_KEY}).mappings().first()
    if not row:
        return _default_registry()
    value = row.get('value')
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except Exception:
            return _default_registry()
    if not isinstance(value, dict):
        return _default_registry()
    value.setdefault('version', 1)
    value.setdefault('models', [])
    return value


def _save_registry(db: Session, registry: dict[str, Any]):
    payload = json.dumps(registry)
    if _dialect_name(db) == 'postgresql':
        db.execute(
            text(
                '''
                INSERT INTO system_state(key, value, updated_at)
                VALUES (:k, CAST(:payload AS jsonb), CURRENT_TIMESTAMP)
                ON CONFLICT (key)
                DO UPDATE SET value = EXCLUDED.value, updated_at = CURRENT_TIMESTAMP
                '''
            ),
            {'k': MODEL_REGISTRY_KEY, 'payload': payload},
        )
    else:
        db.execute(
            text(
                '''
                INSERT INTO system_state(key, value, updated_at)
                VALUES (:k, :payload, CURRENT_TIMESTAMP)
                ON CONFLICT (key)
                DO UPDATE SET value = excluded.value, updated_at = CURRENT_TIMESTAMP
                '''
            ),
            {'k': MODEL_REGISTRY_KEY, 'payload': payload},
        )




def _auth_headers(item: dict[str, Any]) -> dict[str, str]:
    mode = str(item.get('auth_mode') or 'none').lower()
    if mode == 'bearer':
        env_key = str(item.get('api_key_env') or '').strip()
        if not env_key:
            return {}
        import os
        token = str(os.getenv(env_key) or '').strip()
        if not token:
            return {}
        return {'Authorization': f'Bearer {token}'}
    return {}

def get_model_registry(db: Session):
    reg = _load_registry(db)
    return {'ok': True, **reg}


def set_model_registry(db: Session, registry: dict[str, Any]):
    reg = dict(registry or {})
    reg.setdefault('version', 1)
    reg.setdefault('models', [])
    _save_registry(db, reg)
    db.commit()
    return {'ok': True, **reg}


def get_model_registration(db: Session, model_id: str):
    reg = _load_registry(db)
    item = next((m for m in reg.get('models', []) if str(m.get('id')) == str(model_id)), None)
    return {'ok': item is not None, 'item': item}


def check_model_readiness(db: Session, model_id: str):
    info = get_model_registration(db, model_id)
    if not info.get('ok'):
        return {'ok': False, 'error': 'model_not_found'}
    item = info['item']
    provider = str(item.get('provider_type') or '')
    started = int(time.time() * 1000)

    if provider != 'openai_compatible':
        return {
            'ok': True,
            'model_id': model_id,
            'provider_type': provider,
            'status': str(item.get('status') or 'unknown'),
            'latency_ms': 0,
            'note': 'readiness check currently required for openai_compatible only',
        }

    base = str(item.get('base_url') or '').rstrip('/')
    if not base:
        return {'ok': False, 'model_id': model_id, 'error': 'missing_base_url'}

    try:
        # OpenAI-compatible health probe
        headers = _auth_headers(item)
        auth_mode = str(item.get('auth_mode') or 'none')
        r = requests.get(f'{base}/models', headers=headers or None, timeout=4)
        latency = int(time.time() * 1000) - started
        if r.status_code >= 400:
            return {'ok': False, 'model_id': model_id, 'error': f'http_{r.status_code}', 'latency_ms': latency}
        body = {}
        try:
            body = r.json()
        except Exception:
            body = {}
        names = [str((x or {}).get('id') or '') for x in (body.get('data') or [])]
        target = str(item.get('remote_model_id') or '')
        listed = target in names if target else None
        return {
            'ok': True,
            'model_id': model_id,
            'provider_type': provider,
            'latency_ms': latency,
            'base_url': base,
            'target_model': target,
            'target_listed': listed,
            'models_count': len(names),
            'paper_only': bool(item.get('paper_only')),
            'local': bool(item.get('local')),
            'auth_mode': auth_mode,
            'auth_configured': bool(headers) if auth_mode == 'bearer' else True,
        }
    except Exception as exc:
        latency = int(time.time() * 1000) - started
        return {'ok': False, 'model_id': model_id, 'error': str(exc)[:240], 'latency_ms': latency}


def upsert_model_registration(db: Session, item: dict[str, Any]):
    reg = _load_registry(db)
    models = list(reg.get('models') or [])
    mid = str(item.get('id') or '').strip()
    if not mid:
        return {'ok': False, 'error': 'missing_model_id'}
    idx = next((i for i,m in enumerate(models) if str(m.get('id')) == mid), None)
    if idx is None:
        models.append(item)
    else:
        models[idx] = {**models[idx], **item}
    reg['models'] = models
    _save_registry(db, reg)
    db.commit()
    return {'ok': True, 'item': item}
