"""
E2E test fixtures.

Provides httpx-based clients that talk to a running instance of the
application (local dev server by default, or whatever E2E_BASE_URL
points to).

Credentials are read from environment variables. When running locally,
the project's .env file is loaded automatically so that admin credentials
match the running server.

If E2E_USERNAME / E2E_PASSWORD are not set, a temporary test user is
created via the admin API and cleaned up at the end of the session.
"""

import os
from pathlib import Path
from typing import Generator

import httpx
import pytest
from dotenv import load_dotenv

# Load .env from the project root so local runs pick up ADMIN_USERNAME etc.
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(_PROJECT_ROOT / ".env")

# ---------------------------------------------------------------------------
# Configuration from environment
# ---------------------------------------------------------------------------

_DEFAULT_BASE_URL = "http://localhost:8000"
_DEFAULT_ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
_DEFAULT_ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin")

_TOKEN_PATH = "/api/v1/auth/user/token"
_DEFAULT_TIMEOUT = 30.0

_TEST_USER_EMAIL = "e2e-test-user@example.com"
_TEST_USER_PASSWORD = "E2eTestPass-123"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _obtain_token(base_url: str, username: str, password: str) -> str:
    """Authenticate via the OAuth2 password flow and return a bearer token."""
    with httpx.Client(base_url=base_url, timeout=_DEFAULT_TIMEOUT) as client:
        response = client.post(
            _TOKEN_PATH,
            data={"username": username, "password": password},
        )
        response.raise_for_status()
        token: str = response.json()["access_token"]
        return token


# ---------------------------------------------------------------------------
# Fixtures — base URL & plain client
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def base_url() -> str:
    """Base URL of the running application under test."""
    return os.environ.get("E2E_BASE_URL", _DEFAULT_BASE_URL)


@pytest.fixture(scope="function")
def http_client(base_url: str) -> Generator[httpx.Client, None, None]:
    """Unauthenticated httpx client pointed at the application."""
    with httpx.Client(base_url=base_url, timeout=_DEFAULT_TIMEOUT) as client:
        yield client


# ---------------------------------------------------------------------------
# Fixtures — authentication tokens (session-scoped for speed)
# ---------------------------------------------------------------------------


def _get_admin_token(base_url: str) -> str:
    """Obtain admin token (helper, not a fixture to avoid eager resolution)."""
    username = os.environ.get("E2E_ADMIN_USERNAME", _DEFAULT_ADMIN_USERNAME)
    password = os.environ.get("E2E_ADMIN_PASSWORD", _DEFAULT_ADMIN_PASSWORD)
    return _obtain_token(base_url, username, password)


@pytest.fixture(scope="session")
def admin_token(base_url: str) -> str:
    """Bearer token for the superadmin user."""
    return _get_admin_token(base_url)


@pytest.fixture(scope="session")
def auth_token(base_url: str) -> Generator[str, None, None]:
    """Bearer token for a regular (non-admin) user.

    If E2E_USERNAME / E2E_PASSWORD are set, uses those credentials.
    Otherwise, creates a temporary test user via the admin API and
    cleans it up when the session ends.

    Note: This fixture does NOT depend on admin_token to avoid requiring
    admin credentials when E2E_USERNAME/E2E_PASSWORD are provided (e.g.,
    in production smoke tests).
    """
    username = os.environ.get("E2E_USERNAME", "")
    password = os.environ.get("E2E_PASSWORD", "")

    if username and password:
        yield _obtain_token(base_url, username, password)
        return

    # Auto-bootstrap a temporary test user (requires admin credentials)
    admin_tok = _get_admin_token(base_url)
    user_id = None
    with httpx.Client(base_url=base_url, timeout=_DEFAULT_TIMEOUT) as client:
        headers = {"Authorization": f"Bearer {admin_tok}"}
        resp = client.post(
            "/api/v1/admin/users",
            json={"email": _TEST_USER_EMAIL, "password": _TEST_USER_PASSWORD},
            headers=headers,
        )
        if resp.status_code in (200, 201):
            user_id = resp.json()["id"]
        elif resp.status_code == 400:
            # User already exists (leftover from a previous run) — reuse it
            pass
        else:
            resp.raise_for_status()

    token = _obtain_token(base_url, _TEST_USER_EMAIL, _TEST_USER_PASSWORD)
    yield token

    # Teardown: delete the temporary user
    if user_id is not None:
        with httpx.Client(base_url=base_url, timeout=_DEFAULT_TIMEOUT) as client:
            headers = {"Authorization": f"Bearer {admin_tok}"}
            client.delete(f"/api/v1/admin/users/{user_id}", headers=headers)


# ---------------------------------------------------------------------------
# Fixtures — authenticated clients (function-scoped)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="function")
def authed_client(
    base_url: str, auth_token: str
) -> Generator[httpx.Client, None, None]:
    """httpx client with a regular-user Authorization header."""
    with httpx.Client(
        base_url=base_url,
        timeout=_DEFAULT_TIMEOUT,
        headers={"Authorization": f"Bearer {auth_token}"},
    ) as client:
        yield client


@pytest.fixture(scope="function")
def admin_client(
    base_url: str, admin_token: str
) -> Generator[httpx.Client, None, None]:
    """httpx client with an admin Authorization header."""
    with httpx.Client(
        base_url=base_url,
        timeout=_DEFAULT_TIMEOUT,
        headers={"Authorization": f"Bearer {admin_token}"},
    ) as client:
        yield client
