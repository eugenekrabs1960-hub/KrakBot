from pathlib import Path

from app.db.session import engine


def run_migrations():
    migrations_dir = Path(__file__).parent / "migrations"
    files = sorted(migrations_dir.glob("*.sql"))
    with engine.begin() as conn:
        for f in files:
            conn.exec_driver_sql(f.read_text())
            print(f"applied migration: {f.name}")


if __name__ == "__main__":
    run_migrations()
