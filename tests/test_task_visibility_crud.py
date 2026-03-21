"""
Integration tests for task visibility filtering in CRUD functions.
Visibility rules:
- assigned_users is empty → visible to everyone
- assigned_users is non-empty → visible to assigned users + task creator
- user_id=None (admin) → sees all tasks
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from taskmanagement_app.crud.task import create_task, get_tasks
from taskmanagement_app.db.models.user import User
from taskmanagement_app.schemas.task import TaskCreate


def test_due_tasks_crud_visibility_filtering(
    db_session: Session, test_user: dict
) -> None:
    """Test that due tasks filtering respects assigned_users visibility."""
    user1 = User(
        email=f"due_crud_user1_{test_user['email']}",
        hashed_password="hash",
        is_active=True,
        is_admin=False,
    )
    user2 = User(
        email=f"due_crud_user2_{test_user['email']}",
        hashed_password="hash",
        is_active=True,
        is_admin=False,
    )
    admin_user = User(
        email="due_crud_admin@example.com",
        hashed_password="hash",
        is_active=True,
        is_admin=True,
    )

    db_session.add_all([user1, user2, admin_user])
    db_session.commit()
    for user in [user1, user2, admin_user]:
        db_session.refresh(user)

    # Create a task assigned to user1 only, due tomorrow
    tomorrow = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    task_some = TaskCreate(
        title="Due Multi-user Task",
        description="Due tomorrow, assigned to user1 only",
        created_by=admin_user.id,
        assigned_user_ids=[user1.id],
        due_date=tomorrow,
    )

    created_task = create_task(db_session, task_some)

    # User1 should see the task
    user1_tasks = get_tasks(db_session, user_id=user1.id, include_created=False)
    assert created_task.id in [task.id for task in user1_tasks]

    # User2 should NOT see the task
    user2_tasks = get_tasks(db_session, user_id=user2.id, include_created=False)
    assert created_task.id not in [task.id for task in user2_tasks]

    # Admin should see the task as creator
    admin_tasks = get_tasks(db_session, user_id=admin_user.id, include_created=True)
    assert created_task.id in [task.id for task in admin_tasks]

    # Admin should NOT see the task when include_created=False
    admin_assigned_only = get_tasks(
        db_session, user_id=admin_user.id, include_created=False
    )
    assert created_task.id not in [task.id for task in admin_assigned_only]


def test_multiple_assignment_visibility(db_session: Session, test_user: dict) -> None:
    """Test visibility filtering for tasks with different assignment configurations."""
    user1 = User(
        email=f"multi_user1_{test_user['email']}",
        hashed_password="hash",
        is_active=True,
        is_admin=False,
    )
    user2 = User(
        email=f"multi_user2_{test_user['email']}",
        hashed_password="hash",
        is_active=True,
        is_admin=False,
    )
    admin_user = User(
        email="multi_admin@example.com",
        hashed_password="hash",
        is_active=True,
        is_admin=True,
    )

    db_session.add_all([user1, user2, admin_user])
    db_session.commit()
    for user in [user1, user2, admin_user]:
        db_session.refresh(user)

    # Task 1: no assignees → visible to all
    task_open = TaskCreate(
        title="Open Task",
        description="Visible to all users",
        created_by=admin_user.id,
    )
    created_open = create_task(db_session, task_open)

    # Task 2: assigned to user1 only
    task_user1 = TaskCreate(
        title="User1 Only Task",
        description="Assigned to user1 only",
        created_by=admin_user.id,
        assigned_user_ids=[user1.id],
    )
    created_user1 = create_task(db_session, task_user1)

    # Task 3: assigned to user1 and user2
    task_both = TaskCreate(
        title="Both Users Task",
        description="Assigned to user1 and user2",
        created_by=admin_user.id,
        assigned_user_ids=[user1.id, user2.id],
    )
    created_both = create_task(db_session, task_both)

    # User1 should see open, user1-only, and both-users tasks
    user1_tasks = get_tasks(db_session, user_id=user1.id, include_created=False)
    user1_task_ids = [task.id for task in user1_tasks]
    assert created_open.id in user1_task_ids
    assert created_user1.id in user1_task_ids
    assert created_both.id in user1_task_ids

    # User2 should see open and both-users tasks, but NOT user1-only
    user2_tasks = get_tasks(db_session, user_id=user2.id, include_created=False)
    user2_task_ids = [task.id for task in user2_tasks]
    assert created_open.id in user2_task_ids
    assert created_user1.id not in user2_task_ids
    assert created_both.id in user2_task_ids

    # Admin (include_created=True) should see all
    admin_tasks = get_tasks(db_session, user_id=admin_user.id, include_created=True)
    admin_task_ids = [task.id for task in admin_tasks]
    assert created_open.id in admin_task_ids
    assert created_user1.id in admin_task_ids
    assert created_both.id in admin_task_ids

    # Admin (include_created=False) should only see open task
    admin_assigned_only = get_tasks(
        db_session, user_id=admin_user.id, include_created=False
    )
    admin_assigned_ids = [task.id for task in admin_assigned_only]
    assert created_open.id in admin_assigned_ids
    assert created_user1.id not in admin_assigned_ids
    assert created_both.id not in admin_assigned_ids


def test_admin_none_user_sees_all_tasks(db_session: Session, test_user: dict) -> None:
    """Test that admin users (user_id=None) see all tasks regardless of assignment."""
    regular_user = User(
        email=f"admin_none_user_{test_user['email']}",
        hashed_password="hash",
        is_active=True,
        is_admin=False,
    )
    admin_user = User(
        email="admin_none_admin@example.com",
        hashed_password="hash",
        is_active=True,
        is_admin=True,
    )

    db_session.add_all([regular_user, admin_user])
    db_session.commit()
    for user in [regular_user, admin_user]:
        db_session.refresh(user)

    # Task assigned to regular_user only
    task_one = TaskCreate(
        title="Assigned Task",
        description="Assigned to regular user",
        created_by=admin_user.id,
        assigned_user_ids=[regular_user.id],
    )
    created_one = create_task(db_session, task_one)

    # Admin (user_id=None) should see all tasks
    admin_tasks = get_tasks(db_session, user_id=None, include_created=False)
    admin_task_ids = [task.id for task in admin_tasks]
    assert created_one.id in admin_task_ids

    # Regular user should see the task (assigned to them)
    regular_tasks = get_tasks(
        db_session, user_id=regular_user.id, include_created=False
    )
    assert created_one.id in [task.id for task in regular_tasks]
