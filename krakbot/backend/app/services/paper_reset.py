from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.execution.paper_broker import paper_broker


def reset_paper_state(db: Session) -> dict:
    touched = []

    db.execute(text("""
        CREATE TABLE IF NOT EXISTS paper_execution_records_archive (
            archived_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            execution_id VARCHAR(64),
            payload JSONB
        )
    """))
    touched.append('paper_execution_records_archive(create_if_missing)')

    db.execute(text("""
        INSERT INTO paper_execution_records_archive(execution_id, payload)
        SELECT execution_id, payload
        FROM execution_records
        WHERE mode='paper'
    """))
    touched.append('execution_records(mode=paper)->archive')

    db.execute(text("""
        INSERT INTO paper_execution_records_archive(execution_id, payload)
        VALUES ('__reset_marker__', '{"event":"paper_reset"}'::jsonb)
    """))
    touched.append('paper_reset_marker')

    db.execute(text("DELETE FROM execution_records WHERE mode='paper'"))
    touched.append('execution_records(mode=paper)')

    db.execute(text("DELETE FROM lab_positions WHERE mode='paper'"))
    touched.append('lab_positions(mode=paper)')

    db.execute(text("""
        DO $$
        BEGIN
          IF EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_schema='public' AND table_name='positions'
          ) THEN
            BEGIN
              DELETE FROM positions WHERE mode='paper';
            EXCEPTION WHEN undefined_column THEN
              NULL;
            END;
          END IF;
        END $$;
    """))
    touched.append('positions(mode=paper if table/column exists)')

    paper_broker.flatten_all_positions()
    paper_broker.fills = []

    db.commit()
    return {
        'ok': True,
        'paper_baseline': {
            'starting_equity_usd': 10000.0,
            'cash_usd': 10000.0,
            'realized_pnl_usd': 0.0,
            'unrealized_pnl_usd': 0.0,
            'total_equity_usd': 10000.0,
            'cumulative_fees_usd': 0.0,
        },
        'touched_tables': touched,
        'api_path': '/api/settings/paper/reset',
    }
