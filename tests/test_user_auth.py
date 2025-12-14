from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

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
