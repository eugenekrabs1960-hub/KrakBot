from __future__ import annotations

from collections.abc import Callable

from app.execution.gateway import VenueGateway
from app.execution.models import ExecutionReport, OrderIntent
from app.execution.protocols import RiskEvaluator


class AllowAllRisk:
    def evaluate(self, intent: OrderIntent):
        from app.execution.models import RiskDecision

        return RiskDecision(allowed=True)


class NoopPublisher:
    def publish(self, _topic: str, _payload: dict):
        return None


class ExecutionOrchestrator:
    def __init__(
        self,
        gateway: VenueGateway,
        risk: RiskEvaluator | None = None,
        publisher: NoopPublisher | None = None,
    ):
        self.gateway = gateway
        self.risk = risk or AllowAllRisk()
        self.publisher = publisher or NoopPublisher()

    def execute_intent(self, intent: OrderIntent) -> ExecutionReport:
        self.publisher.publish(
            'execution.intent.received',
            {
                'strategy_instance_id': intent.strategy_instance_id,
                'venue': intent.venue_context.venue,
                'market': intent.market,
                'side': intent.side,
                'qty': intent.qty,
            },
        )

        decision = self.risk.evaluate(intent)
        if not decision.allowed:
            self.publisher.publish(
                'execution.risk.blocked',
                {
                    'strategy_instance_id': intent.strategy_instance_id,
                    'venue': intent.venue_context.venue,
                    'reason_code': decision.reason_code,
                    'details': decision.details,
                },
            )
            return ExecutionReport(
                accepted=False,
                error_code='risk_blocked',
                message=decision.reason_code,
                venue_payload={'risk_details': decision.details},
            )

        adapter = self.gateway.get(intent.venue_context.venue)
        report = adapter.submit_order(intent)
        self.publisher.publish(
            'execution.order.completed',
            {
                'strategy_instance_id': intent.strategy_instance_id,
                'venue': intent.venue_context.venue,
                'accepted': report.accepted,
                'error_code': report.error_code,
            },
        )
        return report
