import time
from sqlalchemy import text
from sqlalchemy.orm import Session


class ReconciliationService:
    def run_strategy_recon(self, db: Session, strategy_instance_id: str) -> dict:
        orders = db.execute(
            text("SELECT count(*)::int c FROM orders WHERE strategy_instance_id=:sid"),
            {'sid': strategy_instance_id},
        ).mappings().first()['c']

        executions = db.execute(
            text("SELECT count(*)::int c FROM executions WHERE strategy_instance_id=:sid"),
            {'sid': strategy_instance_id},
        ).mappings().first()['c']

        status = 'ok' if executions <= orders else 'drift_detected'
        details = {
            'orders': orders,
            'executions': executions,
            'rule': 'executions <= orders',
        }
        ts = int(time.time() * 1000)

        db.execute(
            text(
                """
                INSERT INTO reconciliations(strategy_instance_id, kind, status, details, ts)
                VALUES (:sid, 'strategy', :status, CAST(:details AS jsonb), :ts)
                """
            ),
            {'sid': strategy_instance_id, 'status': status, 'details': __import__('json').dumps(details), 'ts': ts},
        )
        db.commit()
        return {'status': status, 'details': details, 'ts': ts}

    def run_global_recon(self, db: Session) -> dict:
        sids = db.execute(text("SELECT id FROM strategy_instances")).mappings().all()
        results = [self.run_strategy_recon(db, r['id']) for r in sids]
        return {'strategies': len(results), 'results': results}
