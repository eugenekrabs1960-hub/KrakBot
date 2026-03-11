from pathlib import Path

from sqlalchemy import create_engine, text

from app.db.migrate import run_migrations


def test_migration_ledger_apply_once_and_checksum_guard(tmp_path: Path):
    migrations_dir = tmp_path / "migrations"
    migrations_dir.mkdir(parents=True)

    m1 = migrations_dir / "0001_init.sql"
    m2 = migrations_dir / "0002_seed.sql"
    m1.write_text("CREATE TABLE sample (id INTEGER PRIMARY KEY, v TEXT);")
    m2.write_text("INSERT INTO sample (id, v) VALUES (1, 'ok');")

    db_path = tmp_path / "migration_test.db"
    test_engine = create_engine(f"sqlite:///{db_path}", future=True)

    out_first: list[str] = []
    run_migrations(engine_override=test_engine, migrations_dir=migrations_dir, output=out_first.append)
    assert any("applied migration: 0001_init.sql" in line for line in out_first)
    assert any("applied migration: 0002_seed.sql" in line for line in out_first)

    with test_engine.begin() as conn:
        count = conn.execute(text("SELECT COUNT(*) FROM migration_ledger")).scalar_one()
        value = conn.execute(text("SELECT v FROM sample WHERE id=1")).scalar_one()
    assert count == 2
    assert value == "ok"

    out_second: list[str] = []
    run_migrations(engine_override=test_engine, migrations_dir=migrations_dir, output=out_second.append)
    assert any("skipped migration (already applied): 0001_init.sql" in line for line in out_second)
    assert any("skipped migration (already applied): 0002_seed.sql" in line for line in out_second)

    # Checksum guard: modify an already-applied migration and ensure hard failure.
    m2.write_text("INSERT INTO sample (id, v) VALUES (1, 'tampered');")

    try:
        run_migrations(engine_override=test_engine, migrations_dir=migrations_dir, output=lambda _: None)
        assert False, "Expected checksum guard to raise RuntimeError"
    except RuntimeError as exc:
        assert "Checksum mismatch" in str(exc)
