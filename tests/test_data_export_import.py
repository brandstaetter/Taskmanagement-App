"""Tests for data export/import feature (issue #190)."""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from taskmanagement_app.crud.data_export import export_data, import_data
from taskmanagement_app.db.models.task import TaskModel, TaskState
from tests.test_utils import TestUserFactory

# ── CRUD-level tests ──


class TestExportData:
    def test_export_empty_db(self, db_session: Session) -> None:
        result = export_data(db_session)
        assert result.version == 1
        assert result.tasks == []
        # Users list may contain pre-seeded users (e.g. superadmin);
        # just verify it's a list.
        assert isinstance(result.users, list)

    def test_export_with_users_and_tasks(self, db_session: Session) -> None:
        user = TestUserFactory.create_test_user(db_session, "export")
        task = TaskModel(
            title="Export Test Task",
            description="A test task",
            state=TaskState.todo,
            created_by=user["id"],
        )
        db_session.add(task)
        db_session.flush()

        result = export_data(db_session)
        assert result.version == 1
        assert len(result.users) >= 1
        assert len(result.tasks) >= 1

        exported_user = next(u for u in result.users if u.email == user["email"])
        assert exported_user.id == user["id"]

        exported_task = next(t for t in result.tasks if t.title == "Export Test Task")
        assert exported_task.created_by == user["id"]
        assert exported_task.state == "todo"

    def test_export_includes_assigned_users(self, db_session: Session) -> None:
        from taskmanagement_app.crud.user import get_user

        user = TestUserFactory.create_test_user(db_session, "assign_export")
        db_user = get_user(db_session, user["id"])
        assert db_user is not None
        task = TaskModel(
            title="Assigned Task",
            description="Has assignees",
            state=TaskState.todo,
            created_by=user["id"],
        )
        task.assigned_users = [db_user]
        db_session.add(task)
        db_session.flush()

        result = export_data(db_session)
        exported_task = next(t for t in result.tasks if t.title == "Assigned Task")
        assert user["id"] in exported_task.assigned_user_ids


class TestImportData:
    def test_import_users(self, db_session: Session) -> None:
        data = {
            "version": 1,
            "users": [
                {
                    "id": 9999,
                    "email": "imported@example.com",
                    "is_active": True,
                    "is_admin": False,
                }
            ],
            "tasks": [],
        }
        result = import_data(db_session, data)
        assert result.users_imported == 1
        assert result.users_skipped == 0

    def test_import_skips_duplicate_users(self, db_session: Session) -> None:
        user = TestUserFactory.create_test_user(db_session, "dup_import")
        data = {
            "version": 1,
            "users": [
                {
                    "id": 9998,
                    "email": user["email"],
                    "is_active": True,
                    "is_admin": False,
                }
            ],
            "tasks": [],
        }
        result = import_data(db_session, data)
        assert result.users_imported == 0
        assert result.users_skipped == 1
        assert result.skipped_items[0].reason == "User with this email already exists"

    def test_import_tasks_with_user_mapping(self, db_session: Session) -> None:
        data = {
            "version": 1,
            "users": [
                {
                    "id": 5000,
                    "email": "mapped_user@example.com",
                    "is_active": True,
                    "is_admin": False,
                }
            ],
            "tasks": [
                {
                    "id": 5001,
                    "title": "Mapped Task",
                    "description": "Task with mapped creator",
                    "state": "todo",
                    "created_by": 5000,
                }
            ],
        }
        result = import_data(db_session, data)
        assert result.users_imported == 1
        assert result.tasks_imported == 1

    def test_import_skips_invalid_state(self, db_session: Session) -> None:
        data = {
            "version": 1,
            "users": [],
            "tasks": [
                {
                    "id": 1,
                    "title": "Bad State",
                    "description": "Invalid",
                    "state": "nonexistent",
                }
            ],
        }
        result = import_data(db_session, data)
        assert result.tasks_skipped == 1
        assert "Invalid state" in result.skipped_items[0].reason

    def test_import_unsupported_version(self, db_session: Session) -> None:
        import pytest

        with pytest.raises(ValueError, match="Unsupported export version"):
            import_data(db_session, {"version": 999})

    def test_import_skips_task_with_missing_creator(self, db_session: Session) -> None:
        """If created_by references a nonexistent user, the task is skipped."""
        data = {
            "version": 1,
            "users": [],
            "tasks": [
                {
                    "id": 1,
                    "title": "Orphan Task",
                    "description": "Creator gone",
                    "state": "todo",
                    "created_by": 99999,
                }
            ],
        }
        result = import_data(db_session, data)
        assert result.tasks_skipped == 1


# ── API-level tests ──


class TestExportImportAPI:
    def test_export_endpoint(self, client: TestClient) -> None:
        response = client.get("/api/v1/admin/data/export")
        assert response.status_code == 200
        data = response.json()
        assert "version" in data
        assert "users" in data
        assert "tasks" in data

    def test_import_endpoint(self, client: TestClient) -> None:
        data = {
            "version": 1,
            "users": [
                {
                    "id": 7000,
                    "email": "api_import@example.com",
                    "is_active": True,
                    "is_admin": False,
                }
            ],
            "tasks": [],
        }
        response = client.post("/api/v1/admin/data/import", json=data)
        assert response.status_code == 200
        result = response.json()
        assert result["users_imported"] == 1

    def test_import_invalid_version(self, client: TestClient) -> None:
        response = client.post("/api/v1/admin/data/import", json={"version": 999})
        assert response.status_code == 400

    def test_roundtrip_export_import(self, client: TestClient) -> None:
        """Export, then import into a fresh context — verify no errors."""
        export_resp = client.get("/api/v1/admin/data/export")
        assert export_resp.status_code == 200
        exported = export_resp.json()

        # Import the same data — users should be skipped (duplicates)
        import_resp = client.post("/api/v1/admin/data/import", json=exported)
        assert import_resp.status_code == 200
        result = import_resp.json()
        # All users should be skipped since they already exist
        assert result["users_skipped"] == len(exported["users"])
