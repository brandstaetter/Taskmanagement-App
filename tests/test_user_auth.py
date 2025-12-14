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
