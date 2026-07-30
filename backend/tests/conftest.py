"""Shared fixtures for integration tests against real Postgres.

Uses the docker-compose Postgres instance (via Settings.database_url) —
not sqlite. Nested transactions + savepoints keep each test isolated even
though the auth service calls db.commit().
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.deps import get_db
from app.main import app


@pytest.fixture(scope="session")
def engine():
    settings = get_settings()
    return create_engine(settings.database_url, pool_pre_ping=True)


@pytest.fixture
def db_session(engine):
    """Request-scoped session whose commits are savepoints; outer txn rolls back."""
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def client(db_session: Session):
    """TestClient with get_db overridden to the per-test rollback session."""

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
