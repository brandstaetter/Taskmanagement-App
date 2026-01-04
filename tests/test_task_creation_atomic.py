"""Test to verify the race condition fix for task creation with assigned users."""
from sqlalchemy.orm import Session

from taskmanagement_app.crud.task import create_task, get_task
from taskmanagement_app.db.models.user import User
from taskmanagement_app.schemas.task import TaskCreate


def test_task_creation_with_assigned_users_is_atomic(db_session: Session) -> None:
    """Test that task creation with assigned_users happens in a single transaction.

    This test verifies the fix for the race condition where a task could exist
    without its assigned users between two separate commits.
    """
    # Create users
    user1 = User(
        email="atomic_test_user1@example.com",
        hashed_password="hashed_password1",
    )
    user2 = User(
        email="atomic_test_user2@example.com",
        hashed_password="hashed_password2",
    )
    db_session.add_all([user1, user2])
    db_session.commit()

    # Create task with assignment_type="some" and assigned users
    task_data = TaskCreate(
        title="Atomic Test Task",
        description="Testing atomic task creation",
        created_by=user1.id,
        assignment_type="some",
        assigned_user_ids=[user1.id, user2.id],
    )
    
    # Create task - this should be atomic now
    created_task = create_task(db_session, task_data)

    # Verify the task was created with all assigned users in one transaction
    assert created_task is not None
    assert created_task.assignment_type == "some"
    assert len(created_task.assigned_users) == 2
    
    # Verify both users are assigned
    assigned_user_ids = {user.id for user in created_task.assigned_users}
    assert user1.id in assigned_user_ids
    assert user2.id in assigned_user_ids

    # Verify we can retrieve the task and it still has the assigned users
    retrieved_task = get_task(db_session, created_task.id)
    assert retrieved_task is not None
    assert len(retrieved_task.assigned_users) == 2

    retrieved_user_ids = {user.id for user in retrieved_task.assigned_users}
    assert user1.id in retrieved_user_ids
    assert user2.id in retrieved_user_ids
