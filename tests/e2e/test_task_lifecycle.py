"""E2E tests — full CRUD lifecycle for tasks.

Tests exercise the running application via HTTP (not the test client),
so the dev server must be up at E2E_BASE_URL (default http://localhost:8000).
"""

import uuid

import httpx

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_TASKS_URL = "/api/v1/tasks"
_ME_URL = "/api/v1/users/me"


def _unique_title(prefix: str = "e2e-task") -> str:
    """Return a collision-free task title."""
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def _get_current_user_id(client: httpx.Client) -> int:
    """Return the authenticated user's ID via GET /users/me."""
    resp = client.get(_ME_URL)
    resp.raise_for_status()
    user_id: int = resp.json()["id"]
    return user_id


def _create_task(
    client: httpx.Client,
    *,
    title: str | None = None,
    description: str = "e2e test task",
    created_by: int | None = None,
) -> dict:
    """Create a task and return the response JSON. Raises on failure."""
    if created_by is None:
        created_by = _get_current_user_id(client)
    payload = {
        "title": title or _unique_title(),
        "description": description,
        "created_by": created_by,
    }
    resp = client.post(_TASKS_URL, json=payload)
    resp.raise_for_status()
    data: dict = resp.json()
    return data


def _delete_task(client: httpx.Client, task_id: int) -> None:
    """Best-effort cleanup: archive (DELETE) the task."""
    client.delete(f"{_TASKS_URL}/{task_id}")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestCreateTask:
    """POST /api/v1/tasks creates a task."""

    def test_create_task(self, authed_client: httpx.Client) -> None:
        title = _unique_title("create")
        task = _create_task(authed_client, title=title, description="verify creation")

        try:
            assert task["title"] == title
            assert task["description"] == "verify creation"
            assert task["state"] == "todo"
            assert "id" in task
            assert task["id"] > 0
        finally:
            _delete_task(authed_client, task["id"])


class TestUpdateTask:
    """PATCH /api/v1/tasks/{id} updates a task."""

    def test_update_task(self, authed_client: httpx.Client) -> None:
        task = _create_task(authed_client)
        task_id = task["id"]

        try:
            new_title = _unique_title("updated")
            resp = authed_client.patch(
                f"{_TASKS_URL}/{task_id}",
                json={"title": new_title, "description": "patched desc"},
            )
            assert resp.status_code == 200
            body = resp.json()
            assert body["title"] == new_title
            assert body["description"] == "patched desc"
            # State should remain unchanged
            assert body["state"] == "todo"
        finally:
            _delete_task(authed_client, task_id)


class TestTaskStateTransitions:
    """POST start -> complete -> DELETE (archive) lifecycle."""

    def test_task_state_transitions(self, authed_client: httpx.Client) -> None:
        task = _create_task(authed_client)
        task_id = task["id"]

        try:
            # 1. Start the task  (todo -> in_progress)
            resp = authed_client.post(f"{_TASKS_URL}/{task_id}/start")
            assert resp.status_code == 200
            body = resp.json()
            assert body["state"] == "in_progress"
            assert body["started_at"] is not None

            # 2. Complete the task  (in_progress -> done)
            resp = authed_client.post(f"{_TASKS_URL}/{task_id}/complete")
            assert resp.status_code == 200
            body = resp.json()
            assert body["state"] == "done"
            assert body["completed_at"] is not None

            # 3. Archive the task  (done -> archived via DELETE)
            resp = authed_client.delete(f"{_TASKS_URL}/{task_id}")
            assert resp.status_code == 200
            body = resp.json()
            assert body["state"] == "archived"
        finally:
            # Cleanup is already done by the archive step; extra call is harmless
            _delete_task(authed_client, task_id)


class TestTaskAppearsInList:
    """Created task is visible in GET /api/v1/tasks."""

    def test_task_appears_in_list(self, authed_client: httpx.Client) -> None:
        task = _create_task(authed_client)
        task_id = task["id"]

        try:
            resp = authed_client.get(_TASKS_URL, params={"show_all": True})
            assert resp.status_code == 200
            tasks = resp.json()
            matching = [t for t in tasks if t["id"] == task_id]
            assert len(matching) == 1, f"Task {task_id} not found in task list"
            assert matching[0]["title"] == task["title"]
        finally:
            _delete_task(authed_client, task_id)
