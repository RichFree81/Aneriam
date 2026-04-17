import pytest
from dotenv import load_dotenv

# Load env vars before any app imports
load_dotenv()

from fastapi.testclient import TestClient
from sqlmodel import Session
from app.main import app
from app.core.database import engine, get_session


@pytest.fixture
def client():
    """Provide a TestClient that uses the test-scoped database session."""
    return TestClient(app)


@pytest.fixture
def db_session():
    """
    Provide a database session that rolls back all changes after each test.
    This ensures tests do not pollute the dev/production database.
    """
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection)

    # Override the FastAPI dependency so all request-scoped DB access
    # goes through the same session/transaction
    def _override_get_session():
        yield session

    app.dependency_overrides[get_session] = _override_get_session

    yield session

    # Rollback everything the test did
    transaction.rollback()
    connection.close()
    app.dependency_overrides.clear()
