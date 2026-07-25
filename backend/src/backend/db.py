"""Connection pool shared by all request handlers."""

import os
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from psycopg import Connection
from psycopg.rows import DictRow, dict_row
from psycopg_pool import ConnectionPool

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql://scout:scout@localhost:5432/scouting"
)

_pool: ConnectionPool[Connection[DictRow]] | None = None


def get_pool() -> ConnectionPool[Connection[DictRow]]:
    global _pool
    if _pool is None:
        _pool = ConnectionPool(
            DATABASE_URL,
            min_size=1,
            max_size=8,
            kwargs={"row_factory": dict_row},
            open=True,
        )
    return _pool


@contextmanager
def db_conn() -> Iterator[Connection[DictRow]]:
    with get_pool().connection() as conn:
        yield conn


def fetch_all(sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    with db_conn() as conn:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]


def fetch_one(sql: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
    with db_conn() as conn:
        row = conn.execute(sql, params).fetchone()
        return dict(row) if row else None
