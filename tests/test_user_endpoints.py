from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from taskmanagement_app.core.auth import create_user_token
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


def test_get_current_user_info(client: TestClient, db_session: Session) -> None:
    email, access_token = create_and_login_user(client, db_session, "Str0ng!Pass1")

    response = client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert response.status_code == 200
    user_data = response.json()
    assert user_data["email"] == email
    assert user_data["is_active"] is True
    assert user_data["is_admin"] is False
    assert "id" in user_data
    assert "created_at" in user_data
    assert "updated_at" in user_data


def test_get_current_user_info_requires_authentication(
    client: TestClient, db_session: Session
) -> None:
    email = f"user_{uuid4()}@example.com"
    user_data = UserCreate(email=email, password="Str0ng!Pass1")
    response = client.post("/api/v1/admin/users", json=user_data.model_dump())
    assert response.status_code == 200

    existing_auth = client.headers.pop("Authorization", None)
    try:
        response = client.get("/api/v1/users/me")
    finally:
        if existing_auth is not None:
            client.headers["Authorization"] = existing_auth

    assert response.status_code == 401


def test_get_current_user_info_inactive_user_forbidden(
    client: TestClient, db_session: Session
) -> None:
    email = f"inactive_{uuid4()}@example.com"
    user_data = UserCreate(email=email, password="Str0ng!Pass1")
    response = client.post("/api/v1/admin/users", json=user_data.model_dump())
    assert response.status_code == 200

    db_user = get_user_by_email(db_session, email=email)
    assert db_user is not None
    db_user.is_active = False
    db_session.commit()

    token = create_user_token(subject=email)
    response = client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "User account is inactive"


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


def test_change_password_weak_new_password_rejected(
    client: TestClient, db_session: Session
) -> None:
    _, access_token = create_and_login_user(client, db_session, "Str0ng!Pass1")

    response = client.put(
        "/api/v1/users/me/password",
        json={
            "current_password": "Str0ng!Pass1",
            "new_password": "weakpass1",
        },
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert response.status_code == 422


def test_change_password_requires_authentication(
    client: TestClient, db_session: Session
) -> None:
    email = f"user_{uuid4()}@example.com"
    user_data = UserCreate(email=email, password="Str0ng!Pass1")
    response = client.post("/api/v1/admin/users", json=user_data.model_dump())
    assert response.status_code == 200

    existing_auth = client.headers.pop("Authorization", None)
    try:
        response = client.put(
            "/api/v1/users/me/password",
            json={
                "current_password": "Str0ng!Pass1",
                "new_password": "N3w!StrongPass",
            },
        )
    finally:
        if existing_auth is not None:
            client.headers["Authorization"] = existing_auth

    assert response.status_code == 401


def test_superadmin_can_get_me_endpoint(client: TestClient) -> None:
    from taskmanagement_app.core.config import get_settings

    settings = get_settings()
    login = client.post(
        "/api/v1/auth/user/token",
        data={"username": settings.ADMIN_USERNAME, "password": settings.ADMIN_PASSWORD},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert login.status_code == 200
    token = login.json()["access_token"]

    response = client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    user_data = response.json()
    assert user_data["email"] == f"{settings.ADMIN_USERNAME}@example.com"
    assert user_data["is_admin"] is True
    assert user_data["is_active"] is True


def test_superadmin_cannot_change_password(client: TestClient) -> None:
    from taskmanagement_app.core.config import get_settings

    settings = get_settings()
    login = client.post(
        "/api/v1/auth/user/token",
        data={"username": settings.ADMIN_USERNAME, "password": settings.ADMIN_PASSWORD},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert login.status_code == 200
    token = login.json()["access_token"]

    response = client.put(
        "/api/v1/users/me/password",
        json={
            "current_password": "irrelevant",
            "new_password": "N3w!StrongPass",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


def test_superadmin_cannot_update_avatar(client: TestClient) -> None:
    from taskmanagement_app.core.config import get_settings

    settings = get_settings()
    login = client.post(
        "/api/v1/auth/user/token",
        data={"username": settings.ADMIN_USERNAME, "password": settings.ADMIN_PASSWORD},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert login.status_code == 200
    token = login.json()["access_token"]

    response = client.put(
        "/api/v1/users/me/avatar",
        json={"avatar_url": "https://example.com/avatar.png"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


def test_change_password_inactive_user_forbidden(
    client: TestClient, db_session: Session
) -> None:
    email = f"inactive_{uuid4()}@example.com"
    user_data = UserCreate(email=email, password="Str0ng!Pass1")
    response = client.post("/api/v1/admin/users", json=user_data.model_dump())
    assert response.status_code == 200

    db_user = get_user_by_email(db_session, email=email)
    assert db_user is not None
    db_user.is_active = False
    db_session.commit()

    token = create_user_token(subject=email)
    response = client.put(
        "/api/v1/users/me/password",
        json={
            "current_password": "Str0ng!Pass1",
            "new_password": "N3w!StrongPass",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "User account is inactive"


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


def test_update_avatar_invalid_url_rejected(
    client: TestClient, db_session: Session
) -> None:
    _, access_token = create_and_login_user(client, db_session, "Str0ng!Pass1")

    response = client.put(
        "/api/v1/users/me/avatar",
        json={"avatar_url": "not-a-url"},
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert response.status_code == 422


def test_update_avatar_requires_authentication(
    client: TestClient, db_session: Session
) -> None:
    email = f"user_{uuid4()}@example.com"
    user_data = UserCreate(email=email, password="Str0ng!Pass1")
    response = client.post("/api/v1/admin/users", json=user_data.model_dump())
    assert response.status_code == 200

    existing_auth = client.headers.pop("Authorization", None)
    try:
        response = client.put(
            "/api/v1/users/me/avatar",
            json={"avatar_url": "https://example.com/avatar.png"},
        )
    finally:
        if existing_auth is not None:
            client.headers["Authorization"] = existing_auth

    assert response.status_code == 401
