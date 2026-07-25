"""API integration tests run against a populated database; they are skipped
cleanly when none is reachable (e.g. unit-only CI without the data volume)."""

import psycopg
import pytest
from backend.db import DATABASE_URL
from fastapi.testclient import TestClient


def _db_ready() -> bool:
    try:
        with psycopg.connect(DATABASE_URL, connect_timeout=2) as conn:
            n = conn.execute("SELECT count(*) FROM matches").fetchone()
            return bool(n and n[0] > 0)
    except Exception:
        return False


DB_READY = _db_ready()


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers", "integration: requires a populated scouting database"
    )


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    if DB_READY:
        return
    skip = pytest.mark.skip(reason="populated scouting database not available")
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip)


@pytest.fixture(scope="session")
def client() -> TestClient:
    from backend.main import app

    return TestClient(app)
