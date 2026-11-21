from __future__ import annotations

import os
from collections.abc import Iterator

import pytest
from dotenv import load_dotenv
from fastapi.testclient import TestClient
from sqlalchemy import text

load_dotenv()

_DEFAULT_TEST_URL = "postgresql+psycopg://brc:brc@localhost:5432/brc_trade_test"
os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL", _DEFAULT_TEST_URL)

from app.config import get_settings  # noqa: E402
from app.db.session import get_engine, get_session_factory, reset_engine  # noqa: E402

get_settings.cache_clear()
reset_engine()

from app.main import app  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _prepare_test_database() -> None:
    from app.db.migrate import run_migrations

    get_settings.cache_clear()
    reset_engine()
    run_migrations()


@pytest.fixture(autouse=True)
def clean_tables() -> Iterator[None]:
    engine = get_engine()
    assert "brc_trade_test" in str(engine.url), (
        f"Refusing to truncate non-test database: {engine.url}"
    )
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE TABLE trades, positions, prices RESTART IDENTITY CASCADE"))
    yield


@pytest.fixture()
def client() -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def db_session() -> Iterator:
    session = get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
