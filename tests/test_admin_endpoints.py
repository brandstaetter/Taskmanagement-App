from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient

from taskmanagement_app.core.auth import create_superadmin_token


def test_admin_db_init_failure_returns_500(client: TestClient) -> None:
    with patch(
        "taskmanagement_app.api.v1.endpoints.admin.Base.metadata.create_all",
        side_effect=RuntimeError("db down"),
    ):
        response = client.post(
            "/api/v1/admin/db/init",
            headers={"Authorization": f"Bearer {create_superadmin_token()}"},
        )

    assert response.status_code == 500
    assert "Failed to initialize database" in response.json()["detail"]


def test_admin_db_migrate_success(client: TestClient) -> None:
    with patch(
        "taskmanagement_app.api.v1.endpoints.admin.subprocess.run",
        return_value=SimpleNamespace(returncode=0, stdout="ok", stderr=""),
    ):
        response = client.post("/api/v1/admin/db/migrate")

    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "Migrations completed successfully"
    assert data["details"] == "ok"


def test_admin_db_migrate_missing_alembic_ini_returns_500(client: TestClient) -> None:
    with patch(
        "taskmanagement_app.api.v1.endpoints.admin.Path.exists",
        return_value=False,
    ):
        response = client.post("/api/v1/admin/db/migrate")

    assert response.status_code == 500
    assert response.json()["detail"] == "alembic.ini not found"


def test_admin_db_migrate_failure_returns_500(client: TestClient) -> None:
    with patch(
        "taskmanagement_app.api.v1.endpoints.admin.subprocess.run",
        return_value=SimpleNamespace(returncode=1, stdout="", stderr="boom"),
    ):
        response = client.post("/api/v1/admin/db/migrate")

    assert response.status_code == 500
    assert "Migration failed" in response.json()["detail"]


def test_admin_db_migrate_unexpected_exception_returns_500(client: TestClient) -> None:
    with patch(
        "taskmanagement_app.api.v1.endpoints.admin.subprocess.run",
        side_effect=RuntimeError("no subprocess"),
    ):
        response = client.post("/api/v1/admin/db/migrate")

    assert response.status_code == 500
    assert "Failed to run migrations" in response.json()["detail"]


def test_admin_create_user_duplicate_email_returns_400(
    client: TestClient,
) -> None:
    payload = {
        "email": "dup_admin@example.com",
        "password": "Str0ng!Pass",
        "is_admin": False,
    }

    first = client.post("/api/v1/admin/users", json=payload)
    assert first.status_code == 200

    second = client.post("/api/v1/admin/users", json=payload)
    assert second.status_code == 400
    assert second.json()["detail"] == "Email already registered"
