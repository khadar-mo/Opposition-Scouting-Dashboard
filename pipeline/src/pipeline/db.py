"""Database helpers for the pipeline."""

from pathlib import Path

import psycopg

from pipeline.config import DATABASE_URL

SCHEMA_PATH = Path(__file__).with_name("schema.sql")


def connect() -> psycopg.Connection:
    return psycopg.connect(DATABASE_URL)


def init_db() -> None:
    """Create all tables (idempotent)."""
    with connect() as conn:
        conn.execute(SCHEMA_PATH.read_text())
    print("schema created")
