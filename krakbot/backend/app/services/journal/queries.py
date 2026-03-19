from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.models.db_models import FeaturePacketDB, DecisionOutputDB, PolicyDecisionDB, ExecutionRecordDB


def recent_decisions(db: Session, limit: int = 50):
    rows = db.query(DecisionOutputDB).order_by(desc(DecisionOutputDB.id)).limit(limit).all()
    return [r.payload for r in rows]


def recent_packets(db: Session, limit: int = 50):
    rows = db.query(FeaturePacketDB).order_by(desc(FeaturePacketDB.generated_at)).limit(limit).all()
    return [r.payload for r in rows]


def recent_policy(db: Session, limit: int = 50):
    rows = db.query(PolicyDecisionDB).order_by(desc(PolicyDecisionDB.evaluated_at)).limit(limit).all()
    return [r.payload for r in rows]


def recent_exec(db: Session, limit: int = 50):
    rows = db.query(ExecutionRecordDB).order_by(desc(ExecutionRecordDB.created_at)).limit(limit).all()
    return [r.payload for r in rows]
