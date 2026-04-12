"""E2E tests — data export and import operations.

Requires admin privileges and a running dev server.
"""

import uuid

import httpx

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_EXPORT_URL = "/api/v1/admin/data/export"
_IMPORT_URL = "/api/v1/admin/data/import"
_TASKS_URL = "/api/v1/tasks"
_ADMIN_USERS_URL = "/api/v1/admin/users"
_ME_URL = "/api/v1/users/me"

# A password that satisfies: >=8 chars, upper, lower, digit, special char
_STRONG_PASSWORD = "E2eTest!42"


def _unique(prefix: str = "e2e") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestExportData:
    """GET /api/v1/admin/data/export returns valid export payload."""

    def test_export_data(self, admin_client: httpx.Client) -> None:
        resp = admin_client.get(_EXPORT_URL)
        assert resp.status_code == 200

        data = resp.json()
        # Must have the expected top-level keys
        assert "version" in data
        assert "users" in data
        assert "tasks" in data

        # version should be a positive integer
        assert isinstance(data["version"], int)
        assert data["version"] >= 1

        # users and tasks should be lists
        assert isinstance(data["users"], list)
        assert isinstance(data["tasks"], list)

        # If there are users, verify each has expected fields
        if data["users"]:
            user = data["users"][0]
            for field in ("id", "email", "is_active", "is_admin"):
                assert field in user, f"Missing field '{field}' in exported user"

        # If there are tasks, verify each has expected fields
        if data["tasks"]:
            task = data["tasks"][0]
            for field in ("id", "title", "description", "state"):
                assert field in task, f"Missing field '{field}' in exported task"


class TestImportExportRoundtrip:
    """Export data, create a task, export again, then import the first snapshot."""

    def test_import_export_roundtrip(
        self, admin_client: httpx.Client, authed_client: httpx.Client
    ) -> None:
        # 1. Create a uniquely named task so we can track it
        tag = _unique("roundtrip")

        # Get the authed user's ID for created_by
        me_resp = authed_client.get(_ME_URL)
        me_resp.raise_for_status()
        user_id = me_resp.json()["id"]

        create_resp = authed_client.post(
            _TASKS_URL,
            json={
                "title": tag,
                "description": "roundtrip test task",
                "created_by": user_id,
            },
        )
        assert create_resp.status_code == 200
        created_task_id = create_resp.json()["id"]

        try:
            # 2. Export — the new task must be in the export
            export_resp = admin_client.get(_EXPORT_URL)
            assert export_resp.status_code == 200
            export_data = export_resp.json()

            # Verify our task appears in the export
            exported_titles = [t["title"] for t in export_data["tasks"]]
            assert tag in exported_titles, f"Task '{tag}' not found in export"

            # 3. Import the same export payload back
            import_resp = admin_client.post(_IMPORT_URL, json=export_data)
            assert import_resp.status_code == 200
            result = import_resp.json()

            # Verify the import result has the expected shape
            assert "users_imported" in result
            assert "users_skipped" in result
            assert "tasks_imported" in result
            assert "tasks_skipped" in result

            # The import processed our tasks (imported or skipped)
            total_processed = result["tasks_imported"] + result["tasks_skipped"]
            assert total_processed >= 1, "Import should process at least one task"

            # Clean up any duplicates created by the import
            list_resp = authed_client.get(_TASKS_URL, params={"show_all": True})
            if list_resp.status_code == 200:
                for t in list_resp.json():
                    if t["title"] == tag and t["id"] != created_task_id:
                        authed_client.delete(f"{_TASKS_URL}/{t['id']}")

        finally:
            # Cleanup — archive the task we created
            authed_client.delete(f"{_TASKS_URL}/{created_task_id}")
