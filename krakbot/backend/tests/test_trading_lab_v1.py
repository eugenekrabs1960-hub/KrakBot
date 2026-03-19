from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_lab_health_and_profiles():
    health = client.get('/api/lab/health')
    assert health.status_code == 200
    body = health.json()
    assert body['ok'] is True

    profiles = client.get('/api/lab/profiles')
    assert profiles.status_code == 200
    assert 'risk' in profiles.json()


def test_run_cycle_and_log_created():
    before = client.get('/api/lab/state').json()['log_count']
    resp = client.post('/api/lab/cycle/run-once', json={'symbol': 'BTC'})
    assert resp.status_code == 200
    cycle = resp.json()
    assert 'packet' in cycle
    assert 'decision' in cycle
    assert 'gate' in cycle

    after = client.get('/api/lab/state').json()['log_count']
    assert after == before + 1


def test_live_mode_requires_arm_or_rejects_execution():
    client.post('/api/lab/mode', json={'execution_mode': 'live_hyperliquid', 'live_armed': False})
    cycle = client.post('/api/lab/cycle/run-once', json={'symbol': 'BTC'}).json()
    if cycle['gate']['allowed']:
        assert cycle['execution']['accepted'] is False
        assert cycle['execution']['reason'] == 'live_mode_not_armed'
