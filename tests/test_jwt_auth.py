from datetime import timedelta
from typing import Generator
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from taskmanagement_app.core.auth import create_admin_token, create_user_token
from taskmanagement_app.core.config import get_settings
from taskmanagement_app.crud.user import create_user
from taskmanagement_app.main import app
from taskmanagement_app.schemas.user import UserCreate


@pytest.fixture()
def raw_client(db_session: Session) -> Generator[TestClient, None, None]:
    from taskmanagement_app.db.session import get_db

    def override_get_db() -> Generator[Session, None, None]:
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    yield client
    client.close()
    app.dependency_overrides.clear()


def test_tasks_401_without_bearer(raw_client: TestClient) -> None:
    response = raw_client.get("/api/v1/tasks")
    assert response.status_code == 401


def test_tasks_401_invalid_token(raw_client: TestClient) -> None:
    response = raw_client.get(
        "/api/v1/tasks",
        headers={"Authorization": "Bearer not-a-jwt"},
    )
    assert response.status_code == 401


def test_tasks_401_expired_token(raw_client: TestClient) -> None:
    expired = create_admin_token(expires_delta=timedelta(minutes=-1))
    response = raw_client.get(
        "/api/v1/tasks",
        headers={"Authorization": f"Bearer {expired}"},
    )
    assert response.status_code == 401


def test_tasks_401_token_missing_exp(raw_client: TestClient) -> None:
    from jose import jwt

    settings = get_settings()
    token = jwt.encode(
        {"sub": "admin", "role": "admin"},
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )
    response = raw_client.get(
        "/api/v1/tasks",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 401


def test_tasks_200_with_user_token(raw_client: TestClient, db_session: Session) -> None:
    email = f"jwt_user_{uuid4()}@example.com"
    password = "Str0ng!Pass"
    create_user(db_session, UserCreate(email=email, password=password))

    token = create_user_token(email)
    response = raw_client.get(
        "/api/v1/tasks",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200


def test_admin_403_with_user_token(raw_client: TestClient, db_session: Session) -> None:
    email = f"jwt_user2_{uuid4()}@example.com"
    password = "Str0ng!Pass"
    create_user(db_session, UserCreate(email=email, password=password))

    token = create_user_token(email)
    response = raw_client.post(
        "/api/v1/admin/db/init",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


def test_admin_db_init_200_with_admin_token(raw_client: TestClient) -> None:
    token = create_admin_token()
    response = raw_client.post(
        "/api/v1/admin/db/init",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
