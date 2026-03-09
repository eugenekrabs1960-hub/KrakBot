from app.services.orchestrator import OrchestratorService


class _FakeDB:
    def __init__(self):
        self.state = {'state': 'stopped'}

    def execute(self, *args, **kwargs):
        class _R:
            def mappings(self):
                return self
            def first(self_inner):
                return {'value': self.state}
        return _R()

    def commit(self):
        pass


def test_orchestrator_has_rules():
    svc = OrchestratorService()
    assert 'stopped' in svc.allowed
    assert 'running' in svc.allowed
    assert 'paused' in svc.allowed
