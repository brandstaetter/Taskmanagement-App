import pytest
from sqlalchemy.orm import Session

from taskmanagement_app.crud.task import create_task, get_tasks, update_task
from taskmanagement_app.db.models.user import User
from taskmanagement_app.schemas.task import TaskCreate, TaskUpdate


def test_create_task_with_assignment(db_session: Session, test_user: dict) -> None:
    """Test creating a task with assignment information."""
    user = User(
        email=f"user0_{test_user['email']}",
        hashed_password="hashed_password",
        is_active=True,
        is_admin=False,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    task_data = TaskCreate(
        title="Test Task",
        description="Test Description",
        created_by=user.id,
        assigned_user_ids=[user.id],
    )

    task = create_task(db_session, task_data)

    assert task.title == "Test Task"
    assert task.created_by == user.id
    assert len(task.assigned_users) == 1
    assert task.assigned_users[0].id == user.id


def test_get_tasks_user_visibility_filtering(
    db_session: Session, test_user: dict
) -> None:
    """Test that users only see tasks they're assigned to or created."""
    user = User(
        email=f"user_{test_user['email']}",
        hashed_password="hashed_password",
        is_active=True,
        is_admin=False,
    )
    admin_user = User(
        email="admin@example.com",
        hashed_password="hashed_password",
        is_active=True,
        is_admin=True,
    )
    db_session.add(user)
    db_session.add(admin_user)
    db_session.commit()
    db_session.refresh(user)
    db_session.refresh(admin_user)

    # Create task assigned to test_user
    task_assigned = TaskCreate(
        title="Assigned Task",
        description="For test user",
        created_by=admin_user.id,
        assigned_user_ids=[user.id],
    )
    created_task_assigned = create_task(db_session, task_assigned)

    # Create task created by test_user (but assigned to admin)
    task_created = TaskCreate(
        title="Created Task",
        description="By test user",
        created_by=user.id,
        assigned_user_ids=[admin_user.id],
    )
    created_task_created = create_task(db_session, task_created)

    # Create task for different user (should not be visible)
    other_user = User(email="other@example.com", hashed_password="hash")
    db_session.add(other_user)
    db_session.commit()
    db_session.refresh(other_user)

    task_other = TaskCreate(
        title="Other Task",
        description="For other user",
        created_by=admin_user.id,
        assigned_user_ids=[other_user.id],
    )
    created_task_other = create_task(db_session, task_other)

    # Test visibility filtering
    visible_tasks = get_tasks(db_session, user_id=user.id, include_created=True)
    visible_task_ids = {task.id for task in visible_tasks}

    # Should see assigned and created tasks
    assert created_task_assigned.id in visible_task_ids
    assert created_task_created.id in visible_task_ids
    # Should not see other user's task
    assert created_task_other.id not in visible_task_ids

    # Test filtering out created tasks
    assigned_only = get_tasks(db_session, user_id=user.id, include_created=False)
    assigned_task_ids = {task.id for task in assigned_only}

    assert created_task_assigned.id in assigned_task_ids
    assert created_task_created.id not in assigned_task_ids


def test_create_task_with_no_assignees(db_session: Session, test_user: dict) -> None:
    """Test creating a task with no assignees (visible to everyone)."""
    user = User(
        email=f"user_any_null_{test_user['email']}",
        hashed_password="hashed_password",
        is_active=True,
        is_admin=False,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    task_data = TaskCreate(
        title="Open Task",
        description="Task with no specific assignment",
        created_by=user.id,
        # No assigned_user_ids
    )

    task = create_task(db_session, task_data)

    assert task.title == "Open Task"
    assert task.created_by == user.id
    assert task.assigned_users == []


def test_get_tasks_no_assignees_visible_to_all(
    db_session: Session, test_user: dict
) -> None:
    """Test that tasks with no assignees are visible to all users."""
    user = User(
        email=f"user2_{test_user['email']}",
        hashed_password="hashed_password",
        is_active=True,
        is_admin=False,
    )
    admin_user = User(
        email="admin2@example.com",
        hashed_password="hashed_password",
        is_active=True,
        is_admin=True,
    )
    db_session.add(user)
    db_session.add(admin_user)
    db_session.commit()
    db_session.refresh(user)
    db_session.refresh(admin_user)

    task_open = TaskCreate(
        title="Open Task",
        description="Visible to all",
        created_by=admin_user.id,
        # No assigned_user_ids
    )
    created_task = create_task(db_session, task_open)

    # Should be visible to any user
    tasks = get_tasks(db_session, user_id=user.id, include_created=False)
    task_ids = {task.id for task in tasks}

    assert created_task.id in task_ids


def test_create_task_with_multiple_assignees(
    db_session: Session, test_user: dict
) -> None:
    """Test creating a task assigned to multiple users."""
    user = User(
        email=f"user3_{test_user['email']}",
        hashed_password="hashed_password",
        is_active=True,
        is_admin=False,
    )
    admin_user = User(
        email="admin3@example.com",
        hashed_password="hashed_password",
        is_active=True,
        is_admin=True,
    )
    db_session.add(user)
    db_session.add(admin_user)
    db_session.commit()
    db_session.refresh(user)
    db_session.refresh(admin_user)

    task_data = TaskCreate(
        title="Multi-user Task",
        description="For multiple users",
        created_by=admin_user.id,
        assigned_user_ids=[user.id, admin_user.id],
    )

    task = create_task(db_session, task_data)

    assert len(task.assigned_users) == 2
    assigned_user_ids = {u.id for u in task.assigned_users}
    assert user.id in assigned_user_ids
    assert admin_user.id in assigned_user_ids


def test_get_tasks_multi_user_assignment_visibility(
    db_session: Session, test_user: dict
) -> None:
    """Test that multi-user assigned tasks are visible to all assigned users."""
    user1 = User(
        email=f"user_multi1_{test_user['email']}",
        hashed_password="hashed_password",
        is_active=True,
        is_admin=False,
    )
    user2 = User(
        email=f"user_multi2_{test_user['email']}",
        hashed_password="hashed_password",
        is_active=True,
        is_admin=False,
    )
    user3 = User(
        email=f"user_multi3_{test_user['email']}",
        hashed_password="hashed_password",
        is_active=True,
        is_admin=False,
    )
    admin_user = User(
        email="admin_multi@example.com",
        hashed_password="hashed_password",
        is_active=True,
        is_admin=True,
    )
    db_session.add_all([user1, user2, user3, admin_user])
    db_session.commit()
    for u in [user1, user2, user3, admin_user]:
        db_session.refresh(u)

    # Create task assigned to user1 and user2 (but not user3)
    task_multi = TaskCreate(
        title="Multi-user Assignment Task",
        description="Assigned to user1 and user2",
        created_by=admin_user.id,
        assigned_user_ids=[user1.id, user2.id],
    )
    created_task = create_task(db_session, task_multi)

    # user1 can see the task
    user1_tasks = get_tasks(db_session, user_id=user1.id, include_created=False)
    assert created_task.id in {t.id for t in user1_tasks}

    # user2 can see the task
    user2_tasks = get_tasks(db_session, user_id=user2.id, include_created=False)
    assert created_task.id in {t.id for t in user2_tasks}

    # user3 CANNOT see the task
    user3_tasks = get_tasks(db_session, user_id=user3.id, include_created=False)
    assert created_task.id not in {t.id for t in user3_tasks}

    # admin can see the task (created by them)
    admin_tasks = get_tasks(db_session, user_id=admin_user.id, include_created=True)
    assert created_task.id in {t.id for t in admin_tasks}

    # admin cannot see when include_created=False (not in assigned_users)
    admin_assigned_only = get_tasks(
        db_session, user_id=admin_user.id, include_created=False
    )
    assert created_task.id not in {t.id for t in admin_assigned_only}


def test_update_task_remove_assignees(db_session: Session, test_user: dict) -> None:
    """Test updating a task to remove all assignees (makes it open to all)."""
    user = User(
        email=f"user_update_any_{test_user['email']}",
        hashed_password="hashed_password",
        is_active=True,
        is_admin=False,
    )
    admin_user = User(
        email="admin_update_any@example.com",
        hashed_password="hashed_password",
        is_active=True,
        is_admin=True,
    )
    db_session.add(user)
    db_session.add(admin_user)
    db_session.commit()
    db_session.refresh(user)
    db_session.refresh(admin_user)

    # Create task initially assigned to one user
    task_data = TaskCreate(
        title="Task to Update",
        description="Initial assignment",
        created_by=admin_user.id,
        assigned_user_ids=[user.id],
    )
    task = create_task(db_session, task_data)
    assert len(task.assigned_users) == 1

    # Update to remove all assignees
    task_update = TaskUpdate(assigned_user_ids=[])

    updated_task = update_task(db_session, task.id, task_update)

    assert updated_task is not None
    assert updated_task.assigned_users == []


def test_update_task_change_assignees(db_session: Session, test_user: dict) -> None:
    """Test updating a task to change its assignees."""
    user1 = User(
        email=f"user_update_one1_{test_user['email']}",
        hashed_password="hashed_password",
        is_active=True,
        is_admin=False,
    )
    user2 = User(
        email=f"user_update_one2_{test_user['email']}",
        hashed_password="hashed_password",
        is_active=True,
        is_admin=False,
    )
    admin_user = User(
        email="admin_update_one@example.com",
        hashed_password="hashed_password",
        is_active=True,
        is_admin=True,
    )
    db_session.add_all([user1, user2, admin_user])
    db_session.commit()
    for u in [user1, user2, admin_user]:
        db_session.refresh(u)

    # Create task with no assignment
    task_data = TaskCreate(
        title="Task to Update",
        description="No initial assignment",
        created_by=admin_user.id,
    )
    task = create_task(db_session, task_data)
    assert task.assigned_users == []

    # Update to assign to user1
    task_update = TaskUpdate(assigned_user_ids=[user1.id])
    updated_task = update_task(db_session, task.id, task_update)

    assert updated_task is not None
    assert len(updated_task.assigned_users) == 1
    assert updated_task.assigned_users[0].id == user1.id

    # Update to change to user2
    task_update2 = TaskUpdate(assigned_user_ids=[user2.id])
    updated_task2 = update_task(db_session, task.id, task_update2)

    assert updated_task2 is not None
    assert len(updated_task2.assigned_users) == 1
    assert updated_task2.assigned_users[0].id == user2.id


def test_update_task_assignment_with_invalid_user_ids(
    db_session: Session, test_user: dict
) -> None:
    """Test that updating assignment fields with invalid user IDs fails properly."""
    user = User(
        email=f"user_update_invalid_{test_user['email']}",
        hashed_password="hashed_password",
        is_active=True,
        is_admin=False,
    )
    admin_user = User(
        email="admin_update_invalid@example.com",
        hashed_password="hashed_password",
        is_active=True,
        is_admin=True,
    )
    db_session.add_all([user, admin_user])
    db_session.commit()
    for u in [user, admin_user]:
        db_session.refresh(u)

    # Create task with no assignment
    task_data = TaskCreate(
        title="Task for Invalid User Tests",
        description="Testing invalid user references",
        created_by=admin_user.id,
    )
    task = create_task(db_session, task_data)

    # Test updating with invalid assigned_user_ids
    with pytest.raises(ValueError, match="User with ID 88888 does not exist"):
        task_update = TaskUpdate(
            assigned_user_ids=[user.id, 88888],  # One valid, one invalid
        )
        update_task(db_session, task.id, task_update)
