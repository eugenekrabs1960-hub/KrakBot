from app.schemas.feature_packet import FeaturePacket
from app.schemas.decision_output import DecisionOutput
from app.services.models.qwen_local_adapter import QwenLocalAdapter


class AnalystRunner:
    def __init__(self):
        self.adapter = QwenLocalAdapter()

    def run(self, packet: FeaturePacket) -> DecisionOutput:
        return self.adapter.analyze(packet)


analyst_runner = AnalystRunner()
