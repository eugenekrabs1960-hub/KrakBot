from sqlalchemy.orm import Session

from app.models.db_models import FeaturePacketDB, DecisionOutputDB, PolicyDecisionDB, ExecutionRecordDB


def write_cycle(db: Session, packet, decision, policy, execution_record: dict | None):
    packet_payload = packet.model_dump(mode='json')
    decision_payload = decision.model_dump(mode='json')
    policy_payload = policy.model_dump(mode='json')

    db.add(FeaturePacketDB(packet_id=packet.packet_id, coin=packet.coin, symbol=packet.symbol, generated_at=packet.generated_at, payload=packet_payload))
    db.add(DecisionOutputDB(packet_id=decision.packet_id, action=decision.action, confidence=decision.confidence, generated_at=decision.generated_at, payload=decision_payload))
    db.add(PolicyDecisionDB(policy_decision_id=policy.policy_decision_id, packet_id=policy.packet_id, final_action=policy.final_action, evaluated_at=policy.evaluated_at, payload=policy_payload))
    if execution_record:
        exec_payload = dict(execution_record)
        if hasattr(exec_payload.get('created_at'), 'isoformat'):
            exec_payload['created_at'] = exec_payload['created_at'].isoformat()
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
            payload=exec_payload,
        ))
    db.commit()
