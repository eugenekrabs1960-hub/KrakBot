from app.core.config import settings
from app.schemas.feature_packet import FeaturePacket
from app.schemas.decision_output import DecisionOutput
from app.services.models.qwen_local_adapter import QwenLocalAdapter
from app.services.models.output_validator import validate_output
from app.services.models.output_repair import repair_output


class AnalystRunner:
    def __init__(self):
        self.adapter = QwenLocalAdapter()

    def run(self, packet: FeaturePacket) -> DecisionOutput:
        decision = self.adapter.analyze(packet)
        ok, _err = validate_output(decision)
        if ok:
            return decision
        if settings.repair_enabled and not settings.llm_disable_repair:
            repaired = repair_output(decision.model_dump(mode='json'), packet_id=packet.packet_id)
            return repaired
        return decision


analyst_runner = AnalystRunner()
