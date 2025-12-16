from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from taskmanagement_app.crud.user import get_user_by_email
from taskmanagement_app.schemas.user import UserCreate


def create_and_login_user(
    client: TestClient, db_session: Session, password: str
) -> tuple[str, str]:
    email = f"user_{uuid4()}@example.com"
    user_data = UserCreate(email=email, password=password)
    response = client.post("/api/v1/admin/users", json=user_data.model_dump())
    assert response.status_code == 200

    token_response = client.post(
        "/api/v1/auth/user/token",
        data={"username": email, "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert token_response.status_code == 200
    access_token = token_response.json()["access_token"]
    return email, access_token


def test_change_password_success(client: TestClient, db_session: Session) -> None:
    email, access_token = create_and_login_user(client, db_session, "Str0ng!Pass1")

    response = client.put(
        "/api/v1/users/me/password",
        json={
            "current_password": "Str0ng!Pass1",
            "new_password": "N3w!StrongPass",
        },
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert response.status_code == 200
    updated_user = response.json()
    assert updated_user["email"] == email

    # Verify new password works
    login_response = client.post(
        "/api/v1/auth/user/token",
        data={"username": email, "password": "N3w!StrongPass"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert login_response.status_code == 200


def test_change_password_incorrect_current_password(
    client: TestClient, db_session: Session
) -> None:
    _, access_token = create_and_login_user(client, db_session, "Str0ng!Pass1")

    response = client.put(
        "/api/v1/users/me/password",
        json={
            "current_password": "WrongPassword1!",
            "new_password": "Anoth3r!Pass",
        },
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Current password is incorrect"


def test_update_avatar(client: TestClient, db_session: Session) -> None:
    email, access_token = create_and_login_user(client, db_session, "Str0ng!Pass1")
    avatar_url = "https://example.com/avatar.png"

    response = client.put(
        "/api/v1/users/me/avatar",
        json={"avatar_url": avatar_url},
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert response.status_code == 200
    updated_user = response.json()
    assert updated_user["avatar_url"] == avatar_url

    db_user = get_user_by_email(db_session, email=email)
    assert db_user is not None
    assert db_user.avatar_url == avatar_url
