from abc import ABC, abstractmethod

from app.schemas.feature_packet import FeaturePacket
from app.schemas.decision_output import DecisionOutput


class LocalModelAdapter(ABC):
    @abstractmethod
    def analyze(self, packet: FeaturePacket) -> DecisionOutput:
        raise NotImplementedError
