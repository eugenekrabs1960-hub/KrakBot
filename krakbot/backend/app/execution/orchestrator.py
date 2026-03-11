from __future__ import annotations

from app.execution.gateway import VenueGateway
from app.execution.models import ExecutionReport, OrderIntent
from app.execution.protocols import RiskEvaluator


class AllowAllRisk:
    def evaluate(self, intent: OrderIntent):
        from app.execution.models import RiskDecision

        return RiskDecision(allowed=True)


class ExecutionOrchestrator:
    def __init__(self, gateway: VenueGateway, risk: RiskEvaluator | None = None):
        self.gateway = gateway
        self.risk = risk or AllowAllRisk()

    def execute_intent(self, intent: OrderIntent) -> ExecutionReport:
        decision = self.risk.evaluate(intent)
        if not decision.allowed:
            return ExecutionReport(
                accepted=False,
                error_code='risk_blocked',
                message=decision.reason_code,
                venue_payload={'risk_details': decision.details},
            )

        adapter = self.gateway.get(intent.venue_context.venue)
        return adapter.submit_order(intent)
