from app.execution.gateway import VenueGateway
from app.execution.models import ExecutionReport, OrderIntent, OrderState, RiskDecision, VenueContext
from app.execution.orchestrator import ExecutionOrchestrator


class _FakeAdapter:
    name = 'fake'

    def __init__(self):
        self.calls = 0

    def submit_order(self, intent: OrderIntent) -> ExecutionReport:
        self.calls += 1
        return ExecutionReport(
            accepted=True,
            order_state=OrderState(
                order_id='ord_1',
                strategy_instance_id=intent.strategy_instance_id,
                venue='fake',
                market=intent.market,
                side=intent.side,
                qty=intent.qty,
                status='accepted',
            ),
        )

    def cancel_order(self, order_id: str) -> dict:
        return {'ok': True, 'order_id': order_id}

    def fetch_account_state(self):
        return None

    def fetch_positions(self):
        return []

    def health(self):
        return {'ok': True}


class _BlockRisk:
    def evaluate(self, _intent: OrderIntent):
        return RiskDecision(allowed=False, reason_code='max_notional', details={'cap': 1000})


class _Publisher:
    def __init__(self):
        self.events = []

    def publish(self, topic: str, payload: dict):
        self.events.append((topic, payload))


def test_gateway_register_and_get():
    g = VenueGateway()
    a = _FakeAdapter()
    g.register('hyperliquid', a)

    assert g.get('hyperliquid') is a
    assert g.list_venues() == ['hyperliquid']


def test_orchestrator_runs_adapter_when_risk_allows():
    g = VenueGateway()
    a = _FakeAdapter()
    g.register('hyperliquid', a)

    pub = _Publisher()
    orch = ExecutionOrchestrator(gateway=g, publisher=pub)
    out = orch.execute_intent(
        OrderIntent(
            strategy_instance_id='inst_1',
            market='SOL-PERP',
            side='buy',
            qty=1.5,
            venue_context=VenueContext(venue='hyperliquid', environment='testnet'),
        )
    )

    assert out.accepted is True
    assert out.order_state is not None
    assert out.order_state.venue == 'fake'
    assert a.calls == 1
    topics = [t for t, _ in pub.events]
    assert topics == ['execution.intent.received', 'execution.order.completed']


def test_orchestrator_blocks_when_risk_denies():
    g = VenueGateway()
    a = _FakeAdapter()
    g.register('hyperliquid', a)

    pub = _Publisher()
    orch = ExecutionOrchestrator(gateway=g, risk=_BlockRisk(), publisher=pub)
    out = orch.execute_intent(
        OrderIntent(
            strategy_instance_id='inst_1',
            market='SOL-PERP',
            side='buy',
            qty=99.0,
            venue_context=VenueContext(venue='hyperliquid', environment='testnet'),
        )
    )

    assert out.accepted is False
    assert out.error_code == 'risk_blocked'
    assert out.message == 'max_notional'
    assert a.calls == 0
    topics = [t for t, _ in pub.events]
    assert topics == ['execution.intent.received', 'execution.risk.blocked']
