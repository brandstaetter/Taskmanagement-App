"""Tests for private tasks feature (issue #23)."""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from taskmanagement_app.core.auth import create_user_token
from taskmanagement_app.crud.task import create_task, get_tasks
from taskmanagement_app.schemas.task import TaskCreate
from tests.test_utils import TestUserFactory


class TestPrivateTasksCRUD:
    """CRUD-level tests for private task visibility."""

    def test_private_tasks_excluded_by_default(self, db_session: Session) -> None:
        """Private tasks should not appear in get_tasks by default."""
        user = TestUserFactory.create_test_user(db_session, "priv_default")
        user_id = user["id"]

        # Create a normal task and a private task
        create_task(
            db_session,
            TaskCreate(
                title="Public Task",
                description="Visible",
                created_by=user_id,
            ),
        )
        create_task(
            db_session,
            TaskCreate(
                title="Private Task",
                description="Hidden",
                is_private=True,
                created_by=user_id,
            ),
        )

        # Default query excludes private
        tasks = get_tasks(db_session, user_id=user_id)
        titles = [t.title for t in tasks]
        assert "Public Task" in titles
        assert "Private Task" not in titles

    def test_private_tasks_visible_with_flag(self, db_session: Session) -> None:
        """Private tasks appear when include_private=True for creator."""
        user = TestUserFactory.create_test_user(db_session, "priv_visible")
        user_id = user["id"]

        create_task(
            db_session,
            TaskCreate(
                title="My Private Task",
                description="Should be visible",
                is_private=True,
                created_by=user_id,
            ),
        )

        tasks = get_tasks(db_session, user_id=user_id, include_private=True)
        titles = [t.title for t in tasks]
        assert "My Private Task" in titles

    def test_private_tasks_not_visible_to_other_users(
        self, db_session: Session
    ) -> None:
        """Private tasks are not visible to users who aren't creator/assignee."""
        creator = TestUserFactory.create_test_user(db_session, "priv_creator")
        other = TestUserFactory.create_test_user(db_session, "priv_other")

        create_task(
            db_session,
            TaskCreate(
                title="Creator Private Task",
                description="Only for creator",
                is_private=True,
                created_by=creator["id"],
            ),
        )

        # Other user should not see it even with include_private=True
        tasks = get_tasks(db_session, user_id=other["id"], include_private=True)
        titles = [t.title for t in tasks]
        assert "Creator Private Task" not in titles

    def test_private_tasks_visible_to_assignee(self, db_session: Session) -> None:
        """Private tasks are visible to assignees with include_private=True."""
        creator = TestUserFactory.create_test_user(db_session, "priv_assignee_creator")
        assignee = TestUserFactory.create_test_user(db_session, "priv_assignee")

        create_task(
            db_session,
            TaskCreate(
                title="Assigned Private Task",
                description="For assignee",
                is_private=True,
                created_by=creator["id"],
                assigned_user_ids=[assignee["id"]],
            ),
        )

        tasks = get_tasks(db_session, user_id=assignee["id"], include_private=True)
        titles = [t.title for t in tasks]
        assert "Assigned Private Task" in titles


class TestPrivateTasksAPI:
    """API-level tests for private tasks."""

    def test_create_private_task(self, client: TestClient, db_session: Session) -> None:
        """POST /tasks with is_private=true creates a private task."""
        user = TestUserFactory.create_test_user(db_session, "api_priv_create")
        response = client.post(
            "/api/v1/tasks",
            json={
                "title": "API Private Task",
                "description": "Test",
                "is_private": True,
                "created_by": user["id"],
            },
        )
        assert response.status_code == 200
        assert response.json()["is_private"] is True

    def test_list_excludes_private_by_default(
        self, client: TestClient, db_session: Session
    ) -> None:
        """GET /tasks excludes private tasks by default."""
        user = TestUserFactory.create_test_user(db_session, "api_priv_list")
        token = create_user_token(user["email"])

        # Create private task
        client.post(
            "/api/v1/tasks",
            json={
                "title": "Hidden Private",
                "description": "Should not appear",
                "is_private": True,
                "created_by": user["id"],
            },
        )

        response = client.get(
            "/api/v1/tasks",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        titles = [t["title"] for t in response.json()]
        assert "Hidden Private" not in titles

    def test_list_includes_private_with_flag(
        self, client: TestClient, db_session: Session
    ) -> None:
        """GET /tasks?include_private=true shows private tasks to creator."""
        user = TestUserFactory.create_test_user(db_session, "api_priv_include")
        token = create_user_token(user["email"])

        client.post(
            "/api/v1/tasks",
            json={
                "title": "Visible Private",
                "description": "Should appear",
                "is_private": True,
                "created_by": user["id"],
            },
        )

        response = client.get(
            "/api/v1/tasks?include_private=true",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        titles = [t["title"] for t in response.json()]
        assert "Visible Private" in titles

    def test_print_private_task_excluded_by_default(
        self, client: TestClient, db_session: Session
    ) -> None:
        """POST /tasks/{id}/print rejects private tasks by default."""
        user = TestUserFactory.create_test_user(db_session, "api_priv_print")
        token = create_user_token(user["email"])

        create_resp = client.post(
            "/api/v1/tasks",
            json={
                "title": "Print Private",
                "description": "No print",
                "is_private": True,
                "created_by": user["id"],
            },
        )
        task_id = create_resp.json()["id"]

        response = client.post(
            f"/api/v1/tasks/{task_id}/print",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403

    def test_print_private_task_allowed_with_flag(
        self, client: TestClient, db_session: Session
    ) -> None:
        """POST /tasks/{id}/print?include_private=true allows printing by creator."""
        user = TestUserFactory.create_test_user(db_session, "api_priv_print_ok")
        token = create_user_token(user["email"])

        create_resp = client.post(
            "/api/v1/tasks",
            json={
                "title": "Printable Private",
                "description": "Can print",
                "is_private": True,
                "created_by": user["id"],
            },
        )
        task_id = create_resp.json()["id"]

        response = client.post(
            f"/api/v1/tasks/{task_id}/print?include_private=true",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200

    def test_print_private_task_blocked_for_non_creator(
        self, client: TestClient, db_session: Session
    ) -> None:
        """POST /tasks/{id}/print is blocked for non-creator/non-assignee."""
        creator = TestUserFactory.create_test_user(db_session, "api_priv_print_creator")
        other = TestUserFactory.create_test_user(db_session, "api_priv_print_other")
        other_token = create_user_token(other["email"])

        create_resp = client.post(
            "/api/v1/tasks",
            json={
                "title": "Creator Only Print",
                "description": "Blocked",
                "is_private": True,
                "created_by": creator["id"],
            },
        )
        task_id = create_resp.json()["id"]

        response = client.post(
            f"/api/v1/tasks/{task_id}/print?include_private=true",
            headers={"Authorization": f"Bearer {other_token}"},
        )
        assert response.status_code == 403

    def test_reassign_private_task_by_creator(
        self, client: TestClient, db_session: Session
    ) -> None:
        """Creator can reassign a private task."""
        creator = TestUserFactory.create_test_user(db_session, "priv_reassign_creator")
        new_assignee = TestUserFactory.create_test_user(db_session, "priv_reassign_new")
        token = create_user_token(creator["email"])

        create_resp = client.post(
            "/api/v1/tasks",
            json={
                "title": "Reassignable Private",
                "description": "Test",
                "is_private": True,
                "created_by": creator["id"],
            },
        )
        task_id = create_resp.json()["id"]

        response = client.patch(
            f"/api/v1/tasks/{task_id}",
            json={"assigned_user_ids": [new_assignee["id"]]},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200

    def test_reassign_private_task_by_other_rejected(
        self, client: TestClient, db_session: Session
    ) -> None:
        """Non-creator/non-assignee cannot reassign a private task."""
        creator = TestUserFactory.create_test_user(db_session, "priv_reject_creator")
        other = TestUserFactory.create_test_user(db_session, "priv_reject_other")
        token = create_user_token(other["email"])

        create_resp = client.post(
            "/api/v1/tasks",
            json={
                "title": "Protected Private",
                "description": "Test",
                "is_private": True,
                "created_by": creator["id"],
            },
        )
        task_id = create_resp.json()["id"]

        response = client.patch(
            f"/api/v1/tasks/{task_id}",
            json={"assigned_user_ids": [other["id"]]},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403

    def test_modify_private_task_fields_by_other_rejected(
        self, client: TestClient, db_session: Session
    ) -> None:
        """Non-creator/non-assignee cannot modify any field of a private task."""
        creator = TestUserFactory.create_test_user(db_session, "priv_mod_creator")
        other = TestUserFactory.create_test_user(db_session, "priv_mod_other")
        token = create_user_token(other["email"])

        create_resp = client.post(
            "/api/v1/tasks",
            json={
                "title": "Immutable Private",
                "description": "Test",
                "is_private": True,
                "created_by": creator["id"],
            },
        )
        task_id = create_resp.json()["id"]

        response = client.patch(
            f"/api/v1/tasks/{task_id}",
            json={"title": "Hacked Title"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403
