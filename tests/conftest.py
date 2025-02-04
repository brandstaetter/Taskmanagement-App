import os
import sys
import time
from typing import Any, Dict, Generator

import pytest
from dotenv import load_dotenv
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from taskmanagement_app.core.config import get_settings
from taskmanagement_app.db.base import Base
from taskmanagement_app.db.session import get_db
from taskmanagement_app.main import app

# Load test environment variables
test_env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "test.env")
load_dotenv(test_env_path)

# Add the parent directory to PYTHONPATH
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

settings = get_settings()

# Test database URL
SQLALCHEMY_TEST_DATABASE_URL = settings.DATABASE_URL


@pytest.fixture(scope="session")
def db_engine() -> Generator[Engine, None, None]:
    """Create a test database engine."""
    engine = create_engine(
        SQLALCHEMY_TEST_DATABASE_URL, connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()  # Ensure all connections are closed
    # Add a small delay to ensure file is released
    time.sleep(0.1)
    try:
        if os.path.exists("./test.db"):
            os.remove("./test.db")
    except PermissionError:
        print("Warning: Could not remove test.db file - it may still be in use")


@pytest.fixture(scope="function")
def db_session(db_engine: Engine) -> Generator[Session, None, None]:
    """Create a test database session."""
    TestingSessionLocal = sessionmaker(
        autocommit=False, autoflush=False, bind=db_engine
    )
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.rollback()
        db.close()


@pytest.fixture(scope="function")
def client(db_session: Session) -> Generator[TestClient, None, None]:
    """Create a test client with a test database session."""

    def override_get_db() -> Generator[Session, None, None]:
        try:
            yield db_session
        finally:
            pass  # Session cleanup is handled by the db_session fixture

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def test_user() -> Dict[str, Any]:
    """Create a test user."""
    return {
        "username": "testuser",
        "email": "test@example.com",
        "password": "testpassword123",
    }
