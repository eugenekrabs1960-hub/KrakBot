from datetime import datetime, timezone
import uuid

from app.schemas.outcome_label import OutcomeLabel


def label_outcome(packet, decision, policy, execution_record: dict | None, latest_price: float) -> OutcomeLabel:
    entry = packet.market_snapshot.mark_price
    net_move = (latest_price / entry - 1.0) if entry else 0.0
    direction_correct = None
    if decision.action == "long":
        direction_correct = net_move > 0
    elif decision.action == "short":
        direction_correct = net_move < 0

    trade_executed = execution_record is not None and execution_record.get("status") == "filled"
    pnl = (execution_record.get("filled_notional_usd", 0) * net_move) if trade_executed else 0.0

    return OutcomeLabel(
        outcome_id=f"out_{uuid.uuid4().hex[:12]}",
        packet_id=packet.packet_id,
        decision_id=packet.packet_id,
        policy_decision_id=policy.policy_decision_id,
        generated_at=datetime.now(timezone.utc),
        coin=packet.coin,
        symbol=packet.symbol,
        decision_action=decision.action,
        policy_result=policy.final_action,
        execution_mode=policy.execution_mode,
        evaluation_horizon="15m",
        decision_timestamp=decision.generated_at,
        evaluation_timestamp=datetime.now(timezone.utc),
        market_outcome={
            "entry_reference_price": entry,
            "close_price_at_horizon": latest_price,
            "max_favorable_excursion_pct": max(0.0, net_move),
            "max_adverse_excursion_pct": min(0.0, net_move),
            "net_move_pct_at_horizon": net_move,
            "invalidation_hit": False,
            "invalidation_hit_timestamp": None,
        },
        trade_outcome={
            "trade_executed": trade_executed,
            "filled_notional_usd": execution_record.get("filled_notional_usd", 0.0) if execution_record else 0.0,
            "realized_pnl_usd_at_horizon": pnl,
            "realized_pnl_pct_at_horizon": net_move if trade_executed else None,
            "fees_usd": 0.0,
            "slippage_bps": 0.0,
        },
        evaluation={
            "direction_correct": direction_correct,
            "move_material": abs(net_move) > 0.002,
            "trade_quality": "good" if direction_correct else "poor" if direction_correct is False else "not_applicable",
            "confidence_calibration": "not_applicable",
            "no_trade_would_have_been_better": None,
            "invalidation_quality": "not_applicable",
            "timing_quality": "acceptable",
            "policy_gate_quality": "correct",
        },
        mistake_tags=[] if direction_correct is not False else ["direction_miss"],
        summary="deterministic_v1_label",
    )
