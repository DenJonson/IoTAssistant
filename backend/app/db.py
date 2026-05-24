import os

import psycopg


DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://iot:iot_dev_password@localhost:5432/iot",
)


def get_connection() -> psycopg.Connection:
    return psycopg.connect(DATABASE_URL)


def check_db_connection() -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 AS ok")
            row = cur.fetchone()

            if row is None or row[0] != 1:
                raise RuntimeError("Database health check failed")