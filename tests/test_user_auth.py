from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from taskmanagement_app.core.config import get_settings
from taskmanagement_app.crud.user import create_user
from taskmanagement_app.schemas.user import UserCreate


def test_user_login_token(client: TestClient, db_session: Session) -> None:
    email = f"login_{uuid4()}@example.com"
    password = "Str0ng!Pass"
    create_user(db_session, UserCreate(email=email, password=password))

    response = client.post(
        "/api/v1/auth/user/token",
        data={"username": email, "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_user_login_token_inactive_user_forbidden(
    client: TestClient, db_session: Session
) -> None:
    from taskmanagement_app.db.models.user import User

    email = f"inactive_{uuid4()}@example.com"
    password = "Str0ng!Pass"
    create_user(db_session, UserCreate(email=email, password=password))

    user = db_session.query(User).filter(User.email == email).first()
    assert user is not None
    user.is_active = False
    db_session.commit()

    response = client.post(
        "/api/v1/auth/user/token",
        data={"username": email, "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert response.status_code == 403


def test_admin_can_login_via_user_token_endpoint(client: TestClient) -> None:
    settings = get_settings()
    response = client.post(
        "/api/v1/auth/user/token",
        data={"username": settings.ADMIN_USERNAME, "password": settings.ADMIN_PASSWORD},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_admin_login_endpoint_removed_returns_404(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/token",
        data={"username": "admin", "password": "admin"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert response.status_code == 404


def test_admin_token_from_user_token_endpoint_has_admin_privileges(
    client: TestClient,
) -> None:
    settings = get_settings()
    login = client.post(
        "/api/v1/auth/user/token",
        data={"username": settings.ADMIN_USERNAME, "password": settings.ADMIN_PASSWORD},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert login.status_code == 200
    token = login.json()["access_token"]

    response = client.post(
        "/api/v1/admin/db/init",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200


def test_db_admin_can_login_and_has_admin_privileges(
    client: TestClient, db_session: Session
) -> None:
    from taskmanagement_app.db.models.user import User

    email = f"db_admin_{uuid4()}@example.com"
    password = "Str0ng!Pass"
    create_user(db_session, UserCreate(email=email, password=password))

    db_user = db_session.query(User).filter(User.email == email).first()
    assert db_user is not None
    db_user.is_admin = True
    db_session.commit()

    login = client.post(
        "/api/v1/auth/user/token",
        data={"username": email, "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert login.status_code == 200
    token = login.json()["access_token"]

    response = client.post(
        "/api/v1/admin/db/init",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403
