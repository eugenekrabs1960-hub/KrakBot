from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path
from typing import Callable

from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.db.session import engine

LEDGER_TABLE = "migration_ledger"
VERSION_RE = re.compile(r"^(\d+)")


def _checksum(sql_text: str) -> str:
    return hashlib.sha256(sql_text.encode("utf-8")).hexdigest()


def _version_from_filename(filename: str) -> int:
    match = VERSION_RE.match(filename)
    if not match:
        raise ValueError(f"Migration filename must start with numeric version: {filename}")
    return int(match.group(1))


def _ensure_ledger(conn) -> None:
    conn.exec_driver_sql(
        f"""
        CREATE TABLE IF NOT EXISTS {LEDGER_TABLE} (
            id INTEGER PRIMARY KEY,
            version INTEGER NOT NULL UNIQUE,
            filename VARCHAR(255) NOT NULL UNIQUE,
            checksum CHAR(64) NOT NULL,
            applied_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )


def run_migrations(
    engine_override: Engine | None = None,
    migrations_dir: str | Path | None = None,
    output: Callable[[str], None] = print,
) -> None:
    selected_engine = engine_override or engine
    selected_dir = Path(migrations_dir or os.getenv("MIGRATIONS_DIR") or (Path(__file__).parent / "migrations"))

    files = sorted(selected_dir.glob("*.sql"))

    with selected_engine.begin() as conn:
        _ensure_ledger(conn)

        for migration_file in files:
            sql_text = migration_file.read_text()
            checksum = _checksum(sql_text)
            version = _version_from_filename(migration_file.name)

            existing = conn.execute(
                text(
                    f"SELECT checksum FROM {LEDGER_TABLE} WHERE version = :version OR filename = :filename"
                ),
                {"version": version, "filename": migration_file.name},
            ).fetchone()

            if existing:
                existing_checksum = existing[0]
                if existing_checksum != checksum:
                    raise RuntimeError(
                        f"Checksum mismatch for {migration_file.name}. "
                        "Migration already applied with different content."
                    )
                output(f"skipped migration (already applied): {migration_file.name}")
                continue

            conn.exec_driver_sql(sql_text)
            conn.execute(
                text(
                    f"INSERT INTO {LEDGER_TABLE} (version, filename, checksum) "
                    "VALUES (:version, :filename, :checksum)"
                ),
                {"version": version, "filename": migration_file.name, "checksum": checksum},
            )
            output(f"applied migration: {migration_file.name}")


if __name__ == "__main__":
    run_migrations()
