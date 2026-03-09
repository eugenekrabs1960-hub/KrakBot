from sqlalchemy import text
from sqlalchemy.orm import Session


class OrchestratorService:
    """Durable bot runtime state machine backed by system_state."""

    allowed = {
        'stopped': {'start'},
        'running': {'pause', 'stop', 'reload'},
        'paused': {'resume', 'stop', 'reload'},
    }

    def get_state(self, db: Session) -> str:
        row = db.execute(text("SELECT value FROM system_state WHERE key='bot'")).mappings().first()
        if not row:
            db.execute(text("INSERT INTO system_state(key, value) VALUES ('bot', '{\"state\":\"stopped\"}'::jsonb)"))
            db.commit()
            return 'stopped'
        return row['value'].get('state', 'stopped')

    def apply_command(self, db: Session, command: str) -> str:
        current = self.get_state(db)
        if command == 'start' and current == 'paused':
            command = 'resume'

        target = {
            'start': 'running',
            'stop': 'stopped',
            'pause': 'paused',
            'resume': 'running',
            'reload': current,
        }.get(command)

        if command != 'reload' and command not in self.allowed.get(current, set()):
            raise ValueError(f'invalid transition: {current} -> {command}')

        db.execute(
            text(
                """
                INSERT INTO system_state(key, value, updated_at)
                VALUES ('bot', jsonb_build_object('state', :state, 'last_command', :cmd), NOW())
                ON CONFLICT (key)
                DO UPDATE SET value = EXCLUDED.value, updated_at = NOW()
                """
            ),
            {'state': target, 'cmd': command},
        )
        db.commit()
        return target
