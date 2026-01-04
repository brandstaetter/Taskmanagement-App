"""
Integration tests for task visibility filtering in CRUD functions.
Tests that assignment_type='some' tasks are properly filtered.
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from taskmanagement_app.crud.task import create_task, get_tasks
from taskmanagement_app.db.models.user import User
from taskmanagement_app.schemas.task import TaskCreate


def test_due_tasks_crud_visibility_filtering(
    db_session: Session, test_user: dict
) -> None:
    """Test that due tasks filtering respects assignment_type='some' visibility."""
    # Create test users
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

    # Create a task with assignment_type='some' assigned to user1 only, due tomorrow
    tomorrow = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    task_some = TaskCreate(
        title="Due Multi-user Task",
        description="Due tomorrow, assigned to user1 only",
        created_by=admin_user.id,
        assignment_type="some",
        assigned_user_ids=[user1.id],
        due_date=tomorrow,
    )

    created_task = create_task(db_session, task_some)

    # Test visibility filtering for each user
    # User1 should see the task
    user1_tasks = get_tasks(db_session, user_id=user1.id, include_created=False)
    user1_task_ids = [task.id for task in user1_tasks]
    assert created_task.id in user1_task_ids, f"User1 should see task {created_task.id}"

    # User2 should NOT see the task
    user2_tasks = get_tasks(db_session, user_id=user2.id, include_created=False)
    user2_task_ids = [task.id for task in user2_tasks]
    assert (
        created_task.id not in user2_task_ids
    ), f"User2 should not see task {created_task.id}"

    # Admin should see the task as creator
    admin_tasks = get_tasks(db_session, user_id=admin_user.id, include_created=True)
    admin_task_ids = [task.id for task in admin_tasks]
    assert created_task.id in admin_task_ids, f"Admin should see task {created_task.id}"

    # Admin should NOT see the task when include_created=False
    admin_assigned_only = get_tasks(
        db_session, user_id=admin_user.id, include_created=False
    )
    admin_assigned_ids = [task.id for task in admin_assigned_only]
    assert (
        created_task.id not in admin_assigned_ids
    ), "Admin should not see task when include_created=False"


def test_multiple_assignment_types_visibility(
    db_session: Session, test_user: dict
) -> None:
    """Test visibility filtering across different assignment types."""
    # Create test users
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

    # Create tasks with different assignment types
    # Task 1: assignment_type='any' - visible to all
    task_any = TaskCreate(
        title="Any Assignment Task",
        description="Visible to all users",
        created_by=admin_user.id,
        assignment_type="any",
    )
    created_any = create_task(db_session, task_any)

    # Task 2: assignment_type='one' assigned to user1
    task_one = TaskCreate(
        title="One Assignment Task",
        description="Assigned to user1 only",
        created_by=admin_user.id,
        assignment_type="one",
        assigned_to=user1.id,
    )
    created_one = create_task(db_session, task_one)

    # Task 3: assignment_type='some' assigned to user1 and user2
    task_some = TaskCreate(
        title="Some Assignment Task",
        description="Assigned to user1 and user2",
        created_by=admin_user.id,
        assignment_type="some",
        assigned_user_ids=[user1.id, user2.id],
    )
    created_some = create_task(db_session, task_some)

    # Test visibility for user1
    user1_tasks = get_tasks(db_session, user_id=user1.id, include_created=False)
    user1_task_ids = [task.id for task in user1_tasks]

    # User1 should see all three tasks
    assert created_any.id in user1_task_ids, "User1 should see 'any' task"
    assert (
        created_one.id in user1_task_ids
    ), "User1 should see 'one' task (assigned to them)"
    assert (
        created_some.id in user1_task_ids
    ), "User1 should see 'some' task (in assigned_users)"

    # Test visibility for user2
    user2_tasks = get_tasks(db_session, user_id=user2.id, include_created=False)
    user2_task_ids = [task.id for task in user2_tasks]

    # User2 should see 'any' and 'some' tasks, but not 'one' task
    assert created_any.id in user2_task_ids, "User2 should see 'any' task"
    assert (
        created_one.id not in user2_task_ids
    ), "User2 should not see 'one' task (assigned to user1)"
    assert (
        created_some.id in user2_task_ids
    ), "User2 should see 'some' task (in assigned_users)"

    # Test visibility for admin (include_created=True)
    admin_tasks = get_tasks(db_session, user_id=admin_user.id, include_created=True)
    admin_task_ids = [task.id for task in admin_tasks]

    # Admin should see all tasks as creator
    assert created_any.id in admin_task_ids, "Admin should see 'any' task (created)"
    assert created_one.id in admin_task_ids, "Admin should see 'one' task (created)"
    assert created_some.id in admin_task_ids, "Admin should see 'some' task (created)"

    # Test visibility for admin (include_created=False)
    admin_assigned_only = get_tasks(
        db_session, user_id=admin_user.id, include_created=False
    )
    admin_assigned_ids = [task.id for task in admin_assigned_only]

    # Admin should see only 'any' task when include_created=False
    assert (
        created_any.id in admin_assigned_ids
    ), "Admin should see 'any' task (assigned to anyone)"
    assert (
        created_one.id not in admin_assigned_ids
    ), "Admin should not see 'one' task (not assigned to admin)"
    assert (
        created_some.id not in admin_assigned_ids
    ), "Admin should not see 'some' task (not in assigned_users)"


def test_admin_none_user_sees_all_tasks(db_session: Session, test_user: dict) -> None:
    """Test that admin users (user_id=None) see all tasks regardless of assignment."""
    # Create test users
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

    # Create tasks with different assignment types
    # Task 1: assignment_type='one' assigned to regular_user
    task_one = TaskCreate(
        title="Admin None One Task",
        description="Assigned to regular user",
        created_by=admin_user.id,
        assignment_type="one",
        assigned_to=regular_user.id,
    )
    created_one = create_task(db_session, task_one)

    # Task 2: assignment_type='some' assigned to regular_user only
    task_some = TaskCreate(
        title="Admin None Some Task",
        description="Assigned to regular user only",
        created_by=admin_user.id,
        assignment_type="some",
        assigned_user_ids=[regular_user.id],
    )
    created_some = create_task(db_session, task_some)

    # Test visibility for admin (user_id=None)
    admin_tasks = get_tasks(db_session, user_id=None, include_created=False)
    admin_task_ids = [task.id for task in admin_tasks]

    # Admin should see all tasks when user_id=None
    assert created_one.id in admin_task_ids, "Admin (None) should see 'one' task"
    assert created_some.id in admin_task_ids, "Admin (None) should see 'some' task"

    # Test visibility for regular user
    regular_tasks = get_tasks(
        db_session, user_id=regular_user.id, include_created=False
    )
    regular_task_ids = [task.id for task in regular_tasks]

    # Regular user should see both tasks (assigned to them)
    assert (
        created_one.id in regular_task_ids
    ), "Regular user should see 'one' task (assigned to them)"
    assert (
        created_some.id in regular_task_ids
    ), "Regular user should see 'some' task (in assigned_users)"
