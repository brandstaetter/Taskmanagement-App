"""Tests for the new admin user-management endpoints:
GET    /api/v1/admin/users
DELETE /api/v1/admin/users/{user_id}
PATCH  /api/v1/admin/users/{user_id}/role
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.test_utils import TestUserFactory

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _create_user(client: TestClient, email_suffix: str = "x") -> Dict[str, Any]:
    payload = {
        "email": f"admin_mgmt_{email_suffix}@example.com",
        "password": "Str0ng!Pass",
        "is_admin": False,
    }
    resp = client.post("/api/v1/admin/users", json=payload)
    assert resp.status_code == 200
    result: Dict[str, Any] = resp.json()
    return result


def _create_task_for_user(client: TestClient, user_id: int) -> Dict[str, Any]:
    payload = {
        "title": "Owned task",
        "description": "desc",
        "due_date": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
        "state": "todo",
        "created_by": user_id,
    }
    resp = client.post("/api/v1/tasks", json=payload)
    assert resp.status_code == 200
    result: Dict[str, Any] = resp.json()
    return result


# ---------------------------------------------------------------------------
# GET /admin/users
# ---------------------------------------------------------------------------


def test_list_users_returns_list(client: TestClient) -> None:
    response = client.get("/api/v1/admin/users")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_list_users_includes_created_user(client: TestClient) -> None:
    import time

    suffix = str(int(time.time() * 1_000_000))
    user = _create_user(client, suffix)
    response = client.get("/api/v1/admin/users")
    assert response.status_code == 200
    ids = [u["id"] for u in response.json()]
    assert user["id"] in ids


def test_list_users_skip_and_limit(client: TestClient, db_session: Session) -> None:
    # Create 3 extra users so we have enough to page
    TestUserFactory.create_multiple_users(db_session, 3, "paging")
    all_users = client.get("/api/v1/admin/users").json()

    if len(all_users) < 2:
        pytest.skip("not enough users to test pagination")

    first = client.get("/api/v1/admin/users", params={"skip": 0, "limit": 1}).json()
    second = client.get("/api/v1/admin/users", params={"skip": 1, "limit": 1}).json()

    assert len(first) == 1
    assert len(second) == 1
    assert first[0]["id"] != second[0]["id"]


def test_list_users_requires_auth(client: TestClient) -> None:
    response = client.get("/api/v1/admin/users", headers={"Authorization": ""})
    assert response.status_code in (401, 403)


# ---------------------------------------------------------------------------
# DELETE /admin/users/{user_id}
# ---------------------------------------------------------------------------


def test_delete_user_success(client: TestClient) -> None:
    import time

    user = _create_user(client, str(int(time.time() * 1_000_000)))
    response = client.delete(f"/api/v1/admin/users/{user['id']}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == user["id"]
    assert data["email"] == user["email"]


def test_delete_user_is_actually_removed(client: TestClient) -> None:
    import time

    user = _create_user(client, str(int(time.time() * 1_000_000)))
    client.delete(f"/api/v1/admin/users/{user['id']}")
    users_after = client.get("/api/v1/admin/users").json()
    assert user["id"] not in [u["id"] for u in users_after]


def test_delete_user_not_found_returns_404(client: TestClient) -> None:
    response = client.delete("/api/v1/admin/users/999999")
    assert response.status_code == 404
    assert response.json()["detail"] == "User not found"


def test_delete_user_with_tasks_returns_409(client: TestClient) -> None:
    import time

    user = _create_user(client, str(int(time.time() * 1_000_000)))
    _create_task_for_user(client, user["id"])

    response = client.delete(f"/api/v1/admin/users/{user['id']}")
    assert response.status_code == 409
    assert "Cannot delete user" in response.json()["detail"]


def test_delete_user_requires_auth(client: TestClient) -> None:
    response = client.delete("/api/v1/admin/users/1", headers={"Authorization": ""})
    assert response.status_code in (401, 403)


# ---------------------------------------------------------------------------
# PATCH /admin/users/{user_id}/role
# ---------------------------------------------------------------------------


def test_update_role_grant_admin(client: TestClient) -> None:
    import time

    user = _create_user(client, str(int(time.time() * 1_000_000)))
    assert user["is_admin"] is False

    response = client.patch(
        f"/api/v1/admin/users/{user['id']}/role", json={"is_admin": True}
    )
    assert response.status_code == 200
    assert response.json()["is_admin"] is True


def test_update_role_revoke_admin(client: TestClient) -> None:
    import time

    payload = {
        "email": f"was_admin_{int(time.time() * 1_000_000)}@example.com",
        "password": "Str0ng!Pass",
        "is_admin": True,
    }
    user = client.post("/api/v1/admin/users", json=payload).json()
    assert user["is_admin"] is True

    response = client.patch(
        f"/api/v1/admin/users/{user['id']}/role", json={"is_admin": False}
    )
    assert response.status_code == 200
    assert response.json()["is_admin"] is False


def test_update_role_not_found_returns_404(client: TestClient) -> None:
    response = client.patch("/api/v1/admin/users/999999/role", json={"is_admin": True})
    assert response.status_code == 404
    assert response.json()["detail"] == "User not found"


def test_update_role_requires_auth(client: TestClient) -> None:
    response = client.patch(
        "/api/v1/admin/users/1/role",
        json={"is_admin": True},
        headers={"Authorization": ""},
    )
    assert response.status_code in (401, 403)


def test_update_role_returns_full_user_schema(client: TestClient) -> None:
    import time

    user = _create_user(client, str(int(time.time() * 1_000_000)))
    response = client.patch(
        f"/api/v1/admin/users/{user['id']}/role", json={"is_admin": True}
    )
    data = response.json()
    assert "id" in data
    assert "email" in data
    assert "is_active" in data
    assert "is_admin" in data
    assert "created_at" in data


# ---------------------------------------------------------------------------
# Gravatar URL in admin responses
# ---------------------------------------------------------------------------


def test_create_user_response_includes_gravatar_url(client: TestClient) -> None:
    import time

    user = _create_user(client, str(int(time.time() * 1_000_000)))
    assert "gravatar_url" in user
    assert user["gravatar_url"] is not None
    assert "gravatar.com" in user["gravatar_url"]


def test_list_users_includes_gravatar_url(client: TestClient) -> None:
    import time

    _create_user(client, str(int(time.time() * 1_000_000)))
    response = client.get("/api/v1/admin/users")
    assert response.status_code == 200
    users = response.json()
    assert len(users) > 0
    for u in users:
        assert "gravatar_url" in u
        assert u["gravatar_url"] is not None
