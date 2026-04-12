"""
Smoke tests — fast, read-only checks that the API is alive and wired up.

Every test in this module is marked ``@pytest.mark.smoke`` so CI can run
the smoke suite independently::

    poetry run pytest -m smoke
"""

import os
from pathlib import Path

import pytest
from dotenv import load_dotenv

# Load .env so admin credentials match the running server.
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(_PROJECT_ROOT / ".env")

_TOKEN_PATH = "/api/v1/auth/user/token"


@pytest.mark.smoke
class TestSmoke:
    """Read-only smoke tests for core API endpoints."""

    # ------------------------------------------------------------------
    # Docs / schema
    # ------------------------------------------------------------------

    def test_swagger_ui_loads(self, http_client):
        """GET /docs returns 200 with Swagger UI HTML."""
        resp = http_client.get("/docs")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        assert "text/html" in resp.headers.get(
            "content-type", ""
        ), "Response should be HTML"
        assert "swagger" in resp.text.lower(), "Page should contain Swagger UI"

    def test_openapi_schema(self, http_client):
        """GET /openapi.json returns 200 with a valid OpenAPI schema."""
        resp = http_client.get("/openapi.json")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        body = resp.json()
        assert "openapi" in body, "Schema must contain 'openapi' version key"
        assert "paths" in body, "Schema must contain 'paths'"
        assert "info" in body, "Schema must contain 'info'"

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    def test_auth_valid_credentials(self, http_client, base_url):
        """POST /api/v1/auth/user/token with valid creds returns a token."""
        # Use E2E credentials (smoke test user), fall back to admin for local dev
        username = os.environ.get("E2E_USERNAME") or os.environ.get(
            "ADMIN_USERNAME", "admin"
        )
        password = os.environ.get("E2E_PASSWORD") or os.environ.get(
            "ADMIN_PASSWORD", "admin"
        )
        resp = http_client.post(
            _TOKEN_PATH,
            data={"username": username, "password": password},
        )
        assert resp.status_code == 200, (
            f"Expected 200 for valid credentials, got {resp.status_code}: "
            f"{resp.text}"
        )
        body = resp.json()
        assert "access_token" in body, "Response must contain 'access_token'"
        assert (
            body.get("token_type", "").lower() == "bearer"
        ), "token_type should be 'bearer'"

    def test_auth_invalid_credentials(self, http_client):
        """POST /api/v1/auth/user/token with bad creds returns 401."""
        resp = http_client.post(
            _TOKEN_PATH,
            data={
                "username": "nonexistent@example.com",
                "password": "wrong_password",
            },
        )
        assert (
            resp.status_code == 401
        ), f"Expected 401 for invalid credentials, got {resp.status_code}"

    # ------------------------------------------------------------------
    # Tasks
    # ------------------------------------------------------------------

    def test_task_list(self, authed_client):
        """GET /api/v1/tasks returns 200 with a list."""
        resp = authed_client.get("/api/v1/tasks")
        assert (
            resp.status_code == 200
        ), f"Expected 200 for task list, got {resp.status_code}: {resp.text}"
        body = resp.json()
        assert isinstance(body, list), "Task list response should be a JSON array"

    # ------------------------------------------------------------------
    # Users
    # ------------------------------------------------------------------

    def test_current_user(self, authed_client):
        """GET /api/v1/users/me returns 200 with user info."""
        resp = authed_client.get("/api/v1/users/me")
        assert (
            resp.status_code == 200
        ), f"Expected 200 for /users/me, got {resp.status_code}: {resp.text}"
        body = resp.json()
        assert "email" in body, "User response must contain 'email'"
        assert "id" in body, "User response must contain 'id'"

    def test_current_user_unauthorized(self, http_client):
        """GET /api/v1/users/me without a token returns 401."""
        resp = http_client.get("/api/v1/users/me")
        assert (
            resp.status_code == 401
        ), f"Expected 401 without auth, got {resp.status_code}"

    def test_user_list(self, authed_client):
        """GET /api/v1/users returns 200 with a list."""
        resp = authed_client.get("/api/v1/users")
        assert (
            resp.status_code == 200
        ), f"Expected 200 for user list, got {resp.status_code}: {resp.text}"
        body = resp.json()
        assert isinstance(body, list), "User list response should be a JSON array"
        assert len(body) >= 1, "User list should contain at least one user"
