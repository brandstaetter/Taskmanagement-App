"""Tests for single-user task assignment."""

import pytest
from sqlalchemy.orm import Session

from taskmanagement_app.crud.task import create_task, get_task
from taskmanagement_app.db.models.user import User
from taskmanagement_app.schemas.task import TaskCreate


def test_create_task_assigned_to_single_user(db_session: Session) -> None:
    """Test creating a task assigned to exactly one user."""
    creator = User(
        email="creator_one@example.com",
        hashed_password="hashed_password",
        is_active=True,
        is_admin=False,
    )
    assigned_user = User(
        email="assigned_one@example.com",
        hashed_password="hashed_password",
        is_active=True,
        is_admin=False,
    )
    other_user = User(
        email="other_one@example.com",
        hashed_password="hashed_password",
        is_active=True,
        is_admin=False,
    )
    db_session.add(creator)
    db_session.add(assigned_user)
    db_session.add(other_user)
    db_session.commit()
    db_session.refresh(creator)
    db_session.refresh(assigned_user)
    db_session.refresh(other_user)

    task_data = TaskCreate(
        title="Single User Task",
        description="Assigned to exactly one user",
        created_by=creator.id,
        assigned_user_ids=[assigned_user.id],
    )

    created_task = create_task(db_session, task_data)

    assert created_task.title == "Single User Task"
    assert created_task.created_by == creator.id
    assert len(created_task.assigned_users) == 1
    assert created_task.assigned_users[0].id == assigned_user.id

    # Verify we can retrieve the task with same assignment
    retrieved_task = get_task(db_session, created_task.id)
    assert retrieved_task is not None
    assert len(retrieved_task.assigned_users) == 1
    assert retrieved_task.assigned_users[0].id == assigned_user.id


def test_create_task_with_no_assigned_user(db_session: Session) -> None:
    """Test creating a task with no assignee (open to all)."""
    creator = User(
        email="creator_no_assign@example.com",
        hashed_password="hashed_password",
        is_active=True,
        is_admin=False,
    )
    db_session.add(creator)
    db_session.commit()
    db_session.refresh(creator)

    task_data = TaskCreate(
        title="Unassigned Task",
        description="No assignee — open to all",
        created_by=creator.id,
    )

    created_task = create_task(db_session, task_data)
    assert created_task.assigned_users == []


def test_create_task_with_invalid_assigned_user(db_session: Session) -> None:
    """Test creating a task with a non-existent assignee fails."""
    creator = User(
        email="creator_invalid@example.com",
        hashed_password="hashed_password",
        is_active=True,
        is_admin=False,
    )
    db_session.add(creator)
    db_session.commit()
    db_session.refresh(creator)

    task_data = TaskCreate(
        title="Invalid Assignment Task",
        description="Assigned to non-existent user",
        created_by=creator.id,
        assigned_user_ids=[99999],  # Non-existent user ID
    )

    with pytest.raises(ValueError, match="User with ID 99999 does not exist"):
        create_task(db_session, task_data)
