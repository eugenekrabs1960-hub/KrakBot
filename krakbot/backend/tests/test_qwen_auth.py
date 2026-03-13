import os
from app.services.model_connectors import _auth_headers


def test_auth_headers_none_mode():
    h = _auth_headers({'auth_mode': 'none'})
    assert h == {}


def test_auth_headers_bearer_mode(monkeypatch):
    monkeypatch.setenv('QWEN_LOCAL_API_KEY', 'abc123')
    h = _auth_headers({'auth_mode': 'bearer', 'api_key_env': 'QWEN_LOCAL_API_KEY'})
    assert h.get('Authorization') == 'Bearer abc123'
