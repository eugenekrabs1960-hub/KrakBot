from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.services.agent_decisions import list_decision_packets, record_decision_packet


def test_record_and_list_packets(tmp_path):
    eng = create_engine(f"sqlite:///{tmp_path/'agent.db'}", future=True)
    with eng.begin() as c:
      c.execute(text("CREATE TABLE agent_decision_packets (id INTEGER PRIMARY KEY AUTOINCREMENT, ts BIGINT, agent_id TEXT, symbol TEXT, action TEXT, confidence DOUBLE, rationale TEXT, context_json TEXT, risk_json TEXT, execution_json TEXT, outcome_json TEXT, created_at TEXT)"))
    Session = sessionmaker(bind=eng, future=True)
    with Session() as db:
        out = record_decision_packet(
            db,
            agent_id='agent_demo',
            symbol='BTC',
            action='buy',
            confidence=0.66,
            rationale='momentum + wallet alignment',
            context={'ret_1': 0.01},
            risk={'allowed': True},
            execution={'accepted': True},
            outcome={'y_ret_fwd_5': 0.002},
        )
        assert out['ok'] is True

        rows = list_decision_packets(db, limit=10, symbol='BTC')
        assert rows['ok'] is True
        assert len(rows['items']) == 1
        assert rows['items'][0]['agent_id'] == 'agent_demo'
