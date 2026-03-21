from unittest.mock import patch

from fastapi.testclient import TestClient

from taskmanagement_app.core.auth import create_superadmin_token


def test_admin_db_init_failure_returns_500(client: TestClient) -> None:
    with (
        patch("taskmanagement_app.api.v1.endpoints.admin.Base.metadata.drop_all"),
        patch(
            "taskmanagement_app.api.v1.endpoints.admin.Base.metadata.create_all",
            side_effect=RuntimeError("db down"),
        ),
    ):
        response = client.post(
            "/api/v1/admin/db/init",
            headers={"Authorization": f"Bearer {create_superadmin_token()}"},
        )

    assert response.status_code == 500
    assert "Failed to initialize database" in response.json()["detail"]


def test_admin_db_migrate_success(client: TestClient) -> None:
    with (
        patch("alembic.command.upgrade"),
        patch(
            "taskmanagement_app.api.v1.endpoints.admin.sa_inspect",
        ) as mock_inspect,
    ):
        mock_inspect.return_value.get_table_names.return_value = [
            "users",
            "tasks",
            "alembic_version",
        ]
        response = client.post("/api/v1/admin/db/migrate")

    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "Migrations completed successfully"


def test_admin_db_migrate_failure_returns_500(client: TestClient) -> None:
    with (
        patch(
            "alembic.command.upgrade",
            side_effect=RuntimeError("boom"),
        ),
        patch(
            "taskmanagement_app.api.v1.endpoints.admin.sa_inspect",
        ) as mock_inspect,
    ):
        mock_inspect.return_value.get_table_names.return_value = [
            "users",
            "alembic_version",
        ]
        response = client.post("/api/v1/admin/db/migrate")

    assert response.status_code == 500
    assert "Failed to run migrations" in response.json()["detail"]


def test_admin_db_migrate_stamps_untracked_db(client: TestClient) -> None:
    with (
        patch("alembic.command.upgrade"),
        patch("alembic.command.stamp") as mock_stamp,
        patch(
            "taskmanagement_app.api.v1.endpoints.admin.sa_inspect",
        ) as mock_inspect,
    ):
        # Tables exist but no alembic_version → should stamp
        mock_inspect.return_value.get_table_names.return_value = ["users", "tasks"]
        response = client.post("/api/v1/admin/db/migrate")

    assert response.status_code == 200
    mock_stamp.assert_called_once()


def test_admin_db_migrate_unexpected_exception_returns_500(client: TestClient) -> None:
    with patch(
        "taskmanagement_app.api.v1.endpoints.admin.sa_inspect",
        side_effect=RuntimeError("no db"),
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
