import os
from pathlib import Path

import psycopg


DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://iot:iot_dev_password@db:5432/iot",
)

MIGRATIONS_DIR = Path(os.getenv("MIGRATIONS_DIR", "/app/migrations"))


def ensure_schema_migrations_table(conn) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version TEXT PRIMARY KEY,
                applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )


def get_applied_versions(conn) -> set[str]:
    with conn.cursor() as cur:
        cur.execute("SELECT version FROM schema_migrations")
        return {row[0] for row in cur.fetchall()}


def apply_migration(conn, migration_path: Path) -> None:
    version = migration_path.name
    sql = migration_path.read_text(encoding="utf-8")

    print(f"applying migration {version}", flush=True)

    with conn.cursor() as cur:
        cur.execute(sql)
        cur.execute(
            """
            INSERT INTO schema_migrations (version)
            VALUES (%s)
            """,
            (version,),
        )


def main() -> None:
    migration_files = sorted(MIGRATIONS_DIR.glob("*.sql"))

    if not migration_files:
        print(f"no migration files found in {MIGRATIONS_DIR}, nothing to apply", flush=True)
        return

    with psycopg.connect(DATABASE_URL) as conn:
        ensure_schema_migrations_table(conn)

        applied_versions = get_applied_versions(conn)

        for migration_path in migration_files:
            if migration_path.name in applied_versions:
                print(f"migration already applied {migration_path.name}", flush=True)
                continue

            apply_migration(conn, migration_path)

        conn.commit()

    print("migrations complete", flush=True)


if __name__ == "__main__":
    main()