from app.services.execution.paper_broker import paper_broker
from app.services.execution.hyperliquid_live_broker import hyperliquid_live_broker


def get_broker(mode: str):
    return paper_broker if mode == "paper" else hyperliquid_live_broker
