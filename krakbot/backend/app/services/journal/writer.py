from sqlalchemy.orm import Session

from app.models.db_models import FeaturePacketDB, DecisionOutputDB, PolicyDecisionDB, ExecutionRecordDB


def write_cycle(db: Session, packet, decision, policy, execution_record: dict | None):
    db.add(FeaturePacketDB(packet_id=packet.packet_id, coin=packet.coin, symbol=packet.symbol, generated_at=packet.generated_at, payload=packet.model_dump()))
    db.add(DecisionOutputDB(packet_id=decision.packet_id, action=decision.action, confidence=decision.confidence, generated_at=decision.generated_at, payload=decision.model_dump()))
    db.add(PolicyDecisionDB(policy_decision_id=policy.policy_decision_id, packet_id=policy.packet_id, final_action=policy.final_action, evaluated_at=policy.evaluated_at, payload=policy.model_dump()))
    if execution_record:
        db.add(ExecutionRecordDB(
            execution_id=execution_record["execution_id"],
            packet_id=packet.packet_id,
            symbol=packet.symbol,
            action=execution_record["action"],
            mode=execution_record["mode"],
            status=execution_record["status"],
            fill_price=execution_record.get("fill_price"),
            filled_notional_usd=execution_record.get("filled_notional_usd"),
            created_at=execution_record["created_at"],
            payload=execution_record,
        ))
    db.commit()
