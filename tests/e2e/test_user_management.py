"""E2E tests — admin user management operations.

Covers user creation, password changes, and role assignment.
Requires the dev server to be running at E2E_BASE_URL.
"""

import uuid

import httpx
import pytest

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_ADMIN_USERS_URL = "/api/v1/admin/users"
_TOKEN_URL = "/api/v1/auth/user/token"
_ME_URL = "/api/v1/users/me"
_ME_PASSWORD_URL = "/api/v1/users/me/password"


def _unique_email() -> str:
    return f"e2e-{uuid.uuid4().hex[:8]}@test.example.com"


# A password that satisfies: >=8 chars, upper, lower, digit, special char
_STRONG_PASSWORD = "E2eTest!42"
_STRONG_PASSWORD_ALT = "AltPass#99"


def _login(base_url: str, email: str, password: str) -> str:
    """Obtain a bearer token for *email* / *password*. Raises on failure."""
    with httpx.Client(base_url=base_url, timeout=30.0) as client:
        resp = client.post(
            _TOKEN_URL,
            data={"username": email, "password": password},
        )
        resp.raise_for_status()
        token: str = resp.json()["access_token"]
        return token


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestAdminCreateUser:
    """Admin creates a user, verifies the user can log in, then deletes."""

    def test_admin_create_user(self, admin_client: httpx.Client, base_url: str) -> None:
        email = _unique_email()
        # 1. Admin creates the user
        resp = admin_client.post(
            _ADMIN_USERS_URL,
            json={"email": email, "password": _STRONG_PASSWORD, "is_admin": False},
        )
        assert resp.status_code == 200
        user = resp.json()
        user_id = user["id"]

        try:
            assert user["email"] == email
            assert user["is_active"] is True
            assert user["is_admin"] is False

            # 2. Verify the new user can log in
            token = _login(base_url, email, _STRONG_PASSWORD)
            assert token  # non-empty string

        finally:
            # 3. Cleanup — admin deletes the user
            del_resp = admin_client.delete(f"{_ADMIN_USERS_URL}/{user_id}")
            assert del_resp.status_code == 200


class TestPasswordChange:
    """User changes their own password, verifies new password works."""

    def test_password_change(self, admin_client: httpx.Client, base_url: str) -> None:
        email = _unique_email()
        # Setup: admin creates a throwaway user
        resp = admin_client.post(
            _ADMIN_USERS_URL,
            json={"email": email, "password": _STRONG_PASSWORD, "is_admin": False},
        )
        assert resp.status_code == 200
        user_id = resp.json()["id"]

        try:
            # 1. Log in as the new user
            token = _login(base_url, email, _STRONG_PASSWORD)
            user_headers = {"Authorization": f"Bearer {token}"}

            with httpx.Client(
                base_url=base_url, timeout=30.0, headers=user_headers
            ) as user_client:
                # 2. Change password
                change_resp = user_client.put(
                    _ME_PASSWORD_URL,
                    json={
                        "current_password": _STRONG_PASSWORD,
                        "new_password": _STRONG_PASSWORD_ALT,
                    },
                )
                assert change_resp.status_code == 200

            # 3. Verify new password works
            new_token = _login(base_url, email, _STRONG_PASSWORD_ALT)
            assert new_token

            # 4. Verify old password no longer works
            with pytest.raises(httpx.HTTPStatusError) as exc_info:
                _login(base_url, email, _STRONG_PASSWORD)
            assert exc_info.value.response.status_code == 401

        finally:
            # Cleanup — admin deletes the user
            admin_client.delete(f"{_ADMIN_USERS_URL}/{user_id}")


class TestRoleAssignment:
    """Admin changes a user's role and verifies the change persists."""

    def test_role_assignment(self, admin_client: httpx.Client) -> None:
        email = _unique_email()
        # Setup: admin creates a non-admin user
        resp = admin_client.post(
            _ADMIN_USERS_URL,
            json={"email": email, "password": _STRONG_PASSWORD, "is_admin": False},
        )
        assert resp.status_code == 200
        user_id = resp.json()["id"]

        try:
            # 1. Promote to admin
            role_resp = admin_client.patch(
                f"{_ADMIN_USERS_URL}/{user_id}/role",
                json={"is_admin": True},
            )
            assert role_resp.status_code == 200
            assert role_resp.json()["is_admin"] is True

            # 2. Verify the change persists by re-fetching the user list
            list_resp = admin_client.get(_ADMIN_USERS_URL)
            assert list_resp.status_code == 200
            users = list_resp.json()
            target = [u for u in users if u["id"] == user_id]
            assert len(target) == 1
            assert target[0]["is_admin"] is True

            # 3. Demote back to regular user (restore original state)
            role_resp = admin_client.patch(
                f"{_ADMIN_USERS_URL}/{user_id}/role",
                json={"is_admin": False},
            )
            assert role_resp.status_code == 200
            assert role_resp.json()["is_admin"] is False

        finally:
            # Cleanup — admin deletes the user
            admin_client.delete(f"{_ADMIN_USERS_URL}/{user_id}")
