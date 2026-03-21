from datetime import datetime, timedelta, timezone
from typing import Any

import pytest
from sqlalchemy.orm import Session

from taskmanagement_app.crud.task import (
    archive_task,
    complete_task,
    create_task,
    get_due_tasks,
    get_random_task,
    get_task,
    get_tasks,
    reset_task_to_todo,
    start_task,
    update_task,
    validate_user_references,
)
from taskmanagement_app.schemas.task import TaskCreate, TaskUpdate
from tests.test_utils import TestUserFactory


def create_test_user(db_session: Session, email_prefix: str = "test_user") -> int:
    """Create a test user and return their ID."""
    user = TestUserFactory.create_test_user(db_session, email_prefix)
    return int(user["id"])


def test_create_task(db_session: Session) -> None:
    user_id = create_test_user(db_session, "test_create_task")

    task_in = TaskCreate(
        title="Test Task",
        description="Test Description",
        due_date=(datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
        state="todo",
        created_by=user_id,
    )
    task = create_task(db=db_session, task=task_in)
    assert task.title == task_in.title
    assert task.description == task_in.description
    assert task.state == task_in.state


def test_get_task(db_session: Session) -> None:
    user_id = create_test_user(db_session, "test_get_task")
    task_in = TaskCreate(
        title="Test Task",
        description="Test Description",
        due_date=(datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
        state="todo",
        created_by=user_id,
    )
    task = create_task(db=db_session, task=task_in)
    stored_task = get_task(db=db_session, task_id=task.id)
    assert stored_task
    assert task.id == stored_task.id
    assert task.title == stored_task.title
    assert task.description == stored_task.description


def test_get_tasks(db_session: Session) -> None:
    user_id = create_test_user(db_session, "test_get_tasks")
    task_in1 = TaskCreate(
        title="Test Task 1",
        description="Test Description 1",
        due_date=(datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
        state="todo",
        created_by=user_id,
    )
    task_in2 = TaskCreate(
        title="Test Task 2",
        description="Test Description 2",
        due_date=(datetime.now(timezone.utc) + timedelta(days=2)).isoformat(),
        state="todo",
        created_by=user_id,
    )
    task1 = create_task(db=db_session, task=task_in1)
    task2 = create_task(db=db_session, task=task_in2)
    tasks = get_tasks(db=db_session)
    assert len(tasks) >= 2
    assert any(t.id == task1.id for t in tasks)
    assert any(t.id == task2.id for t in tasks)


def test_update_task(db_session: Session) -> None:
    user_id = create_test_user(db_session, "test_update_task")
    task_in = TaskCreate(
        title="Test Task",
        description="Test Description",
        due_date=(datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
        state="todo",
        created_by=user_id,
    )
    task = create_task(db=db_session, task=task_in)

    task_update = TaskUpdate(
        title="Updated Task",
        description="Updated Description",
    )
    updated_task = update_task(db=db_session, task_id=task.id, task=task_update)
    assert updated_task
    assert updated_task.title == task_update.title
    assert updated_task.description == task_update.description


def test_archive_task(db_session: Session) -> None:
    user_id = create_test_user(db_session, "test_archive_task")
    task_in = TaskCreate(
        title="Test Task",
        description="Test Description",
        due_date=(datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
        state="done",
        created_by=user_id,
    )
    task = create_task(db=db_session, task=task_in)
    archived_task = archive_task(db=db_session, task_id=task.id)
    assert archived_task
    assert archived_task.id == task.id
    assert archived_task.state == "archived"
    stored_task = get_task(db=db_session, task_id=task.id)
    assert stored_task
    assert stored_task.state == "archived"


def test_task_state_transitions(db_session: Session) -> None:
    user_id = create_test_user(db_session, "test_task_state_transitions")
    task_in = TaskCreate(
        title="Test Task",
        description="Test Description",
        due_date=(datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
        state="todo",
        created_by=user_id,
    )
    task = create_task(db=db_session, task=task_in)

    # Start task
    started_task = start_task(db=db_session, task=task)
    assert started_task.state == "in_progress"
    assert started_task.started_at is not None

    # Complete task
    completed_task = complete_task(db=db_session, task=started_task)
    assert completed_task.state == "done"
    assert completed_task.completed_at is not None


def test_task_state_archived(db_session: Session) -> None:
    """Test task archival functionality."""
    user_id = create_test_user(db_session, "test_task_state_archived")
    task_in = TaskCreate(
        title="Test Task",
        description="Test Description",
        due_date=(datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
        state="todo",
        created_by=user_id,
    )
    task = create_task(db=db_session, task=task_in)

    # Start task
    started_task = start_task(db=db_session, task=task)
    assert started_task.state == "in_progress"

    # Complete task
    completed_task = complete_task(db=db_session, task=started_task)
    assert completed_task.state == "done"

    # Archive task
    archived_task = update_task(
        db=db_session, task_id=completed_task.id, task=TaskUpdate(state="archived")
    )
    assert archived_task is not None
    assert archived_task.state == "archived"

    # Verify task appears in get_tasks when including archived tasks
    all_tasks = get_tasks(db=db_session, include_archived=True)
    assert any(t.id == archived_task.id for t in all_tasks)

    # Verify task doesn't appear in get_tasks when excluding archived tasks
    active_tasks = get_tasks(db=db_session, include_archived=False)
    assert not any(t.id == archived_task.id for t in active_tasks)

    # Verify task doesn't appear in due tasks
    due_tasks = get_due_tasks(db=db_session)
    assert not any(t.id == archived_task.id for t in due_tasks)


def test_get_tasks_with_invalid_dates(db_session: Session) -> None:
    """Test that tasks with invalid dates are handled correctly."""
    user_id = create_test_user(db_session, "test_get_tasks_with_invalid_dates")
    task_in = TaskCreate(
        title="Test Task",
        description="Test Description",
        state="todo",
        created_by=user_id,
    )
    task = create_task(db=db_session, task=task_in)
    task.due_date = "invalid-date"
    db_session.commit()

    # Test get_tasks still works
    tasks = get_tasks(db=db_session)
    assert any(t.id == task.id for t in tasks)

    # Test get_due_tasks handles invalid date
    due_tasks = get_due_tasks(db=db_session)
    assert not any(t.id == task.id for t in due_tasks)


def test_get_random_task(db_session: Session) -> None:
    user_id = create_test_user(db_session, "test_get_random_task")
    # Create multiple tasks
    tasks = []
    for i in range(5):
        task_in = TaskCreate(
            title=f"Task {i}",
            description=f"Description {i}",
            due_date=(datetime.now(timezone.utc) + timedelta(days=i + 1)).isoformat(),
            state="todo",
            created_by=user_id,
        )
        tasks.append(create_task(db=db_session, task=task_in))

    # Complete one task
    start_task(db=db_session, task=tasks[0])
    completed_task = complete_task(db=db_session, task=tasks[0])
    assert completed_task.state == "done"

    # Archive one task
    archived_task = update_task(
        db=db_session, task_id=tasks[1].id, task=TaskUpdate(state="archived")
    )
    assert archived_task is not None and archived_task.state == "archived"

    # Get random task multiple times
    selected_ids = set()
    for _ in range(20):  # Try multiple times to get different tasks
        task = get_random_task(db=db_session)
        if task:
            selected_ids.add(task.id)
            # Verify we never get completed or archived tasks
            assert task.state not in ["done", "archived"]

    # Verify we got at least 2 different tasks
    assert len(selected_ids) >= 2


def test_get_random_due_task(db_session: Session, monkeypatch: Any) -> None:
    """Test random due task selection functionality with deterministic mock."""
    # Create a user first for the tasks
    user_id = create_test_user(db_session, "test_get_random_due_task")

    # Create tasks with different due dates
    tasks = []
    for i in range(5):
        task_in = TaskCreate(
            title=f"Task {i}",
            description=f"Description {i}",
            due_date=(datetime.now(timezone.utc) + timedelta(hours=i)).isoformat(),
            state="todo",
            created_by=user_id,
        )
        tasks.append(create_task(db=db_session, task=task_in))

    # Create a task due in far future
    future_task_in = TaskCreate(
        title="Future Task",
        description="Due in far future",
        due_date=(datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
        state="todo",
        created_by=user_id,
    )
    future_task = create_task(db=db_session, task=future_task_in)

    # Mock random.choices to return deterministic results
    # First return the future task (lowest weight), then return other tasks
    mock_choices_calls = []

    def mock_choices(tasks_list, weights, k=1):
        mock_choices_calls.append((tasks_list, weights))
        if len(mock_choices_calls) == 1:
            return [future_task]
        elif len(mock_choices_calls) == 2:
            return [tasks[0]]
        else:
            return [tasks[1]]

    monkeypatch.setattr("random.choices", mock_choices)

    # Test deterministic selection
    selected_tasks = []
    for _ in range(3):
        task = get_random_task(db=db_session)
        if task:
            selected_tasks.append(task)

    # Verify we got the expected tasks in the expected order
    assert len(selected_tasks) == 3
    assert selected_tasks[0].id == future_task.id  # Future task selected first
    assert selected_tasks[1].id == tasks[0].id  # Then first task
    assert selected_tasks[2].id == tasks[1].id  # Then second task

    # Verify random.choices was called with correct weights
    assert len(mock_choices_calls) == 3
    # Check that weights were calculated (future task should have lowest weight)
    called_tasks, called_weights = mock_choices_calls[0]

    # Find the index of future task in the called tasks
    future_task_index = called_tasks.index(future_task)
    future_task_weight = called_weights[future_task_index]

    # Future task should have the lowest weight (close to 1.0)
    assert future_task_weight < 10.0  # Much lower than tasks due sooner


def test_validate_user_references_with_valid_users(db_session: Session) -> None:
    """Test validation passes when all user references exist."""
    user_id = create_test_user(
        db_session, "test_validate_user_references_with_valid_users"
    )

    # Test TaskCreate with valid user
    task_in = TaskCreate(
        title="Test Task",
        description="Test Description",
        created_by=user_id,
    )
    # Should not raise an exception
    validate_user_references(db=db_session, task_data=task_in)

    # Test TaskUpdate with valid user
    task_update = TaskUpdate(assigned_user_ids=[user_id])
    # Should not raise an exception
    validate_user_references(db=db_session, task_data=task_update)

    # Test dict with valid users
    task_dict = {"created_by": user_id, "assigned_user_ids": [user_id]}
    # Should not raise an exception
    validate_user_references(db=db_session, task_data=task_dict)


def test_validate_user_references_with_invalid_created_by(db_session: Session) -> None:
    """Test validation fails when created_by user doesn't exist."""
    task_in = TaskCreate(
        title="Test Task",
        description="Test Description",
        created_by=99999,  # Non-existent user ID
    )

    with pytest.raises(ValueError, match="User with ID 99999 does not exist"):
        validate_user_references(db=db_session, task_data=task_in)


def test_validate_user_references_with_invalid_assigned_user_ids_single(
    db_session: Session,
) -> None:
    """Test validation fails when assigned_user_ids contain non-existent users."""
    task_update = TaskUpdate(assigned_user_ids=[99999])  # Non-existent user ID

    with pytest.raises(ValueError, match="User with ID 99999 does not exist"):
        validate_user_references(db=db_session, task_data=task_update)


def test_validate_user_references_with_invalid_assigned_user_ids(
    db_session: Session,
) -> None:
    """Test validation fails when assigned_user_ids contain non-existent users."""
    task_update = TaskUpdate(assigned_user_ids=[99999, 99998])  # Non-existent user IDs

    with pytest.raises(ValueError, match="User with ID 99999 does not exist"):
        validate_user_references(db=db_session, task_data=task_update)


def test_create_task_with_invalid_user_reference(db_session: Session) -> None:
    """Test create_task fails when user references don't exist."""
    task_in = TaskCreate(
        title="Test Task",
        description="Test Description",
        created_by=99999,  # Non-existent user ID
    )

    with pytest.raises(ValueError, match="User with ID 99999 does not exist"):
        create_task(db=db_session, task=task_in)


def test_update_task_with_invalid_user_reference(db_session: Session) -> None:
    """Test update_task fails when user references don't exist."""
    user_id = create_test_user(
        db_session, "test_update_task_with_invalid_user_reference"
    )

    task_in = TaskCreate(
        title="Test Task",
        description="Test Description",
        created_by=user_id,
    )
    task = create_task(db=db_session, task=task_in)

    # Try to update with invalid user reference
    task_update = TaskUpdate(assigned_user_ids=[99999])  # Non-existent user ID

    with pytest.raises(ValueError, match="User with ID 99999 does not exist"):
        update_task(db=db_session, task_id=task.id, task=task_update)


def test_validate_user_references_with_none_values(db_session: Session) -> None:
    """Test validation passes when user reference fields are None."""
    user_id = create_test_user(
        db_session, "test_validate_user_references_with_none_values"
    )

    task_in = TaskCreate(
        title="Test Task",
        description="Test Description",
        created_by=user_id,  # Valid user
        assigned_user_ids=None,
    )
    # Should not raise an exception
    validate_user_references(db=db_session, task_data=task_in)

    # Test TaskUpdate with None values
    task_update = TaskUpdate(assigned_user_ids=None)
    # Should not raise an exception
    validate_user_references(db=db_session, task_data=task_update)


def test_validate_user_references_with_empty_list(db_session: Session) -> None:
    """Test validation passes when assigned_user_ids is empty list."""
    task_update = TaskUpdate(assigned_user_ids=[])
    # Should not raise an exception
    validate_user_references(db=db_session, task_data=task_update)


def test_update_task_assigned_user_ids(db_session: Session) -> None:
    """Test updating task's assigned_user_ids."""
    user_id = create_test_user(db_session, "test_assignment_validation")

    task_in = TaskCreate(
        title="Test Task",
        description="Test Description",
        due_date=(datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
        state="todo",
        created_by=user_id,
    )
    task = create_task(db=db_session, task=task_in)
    assert task.assigned_users == []

    # Assign to user
    task_update_valid = TaskUpdate(assigned_user_ids=[user_id])
    updated_task = update_task(db=db_session, task_id=task.id, task=task_update_valid)
    assert updated_task is not None
    assert len(updated_task.assigned_users) == 1
    assert updated_task.assigned_users[0].id == user_id

    # Clear assignees
    task_update_clear = TaskUpdate(assigned_user_ids=[])
    cleared_task = update_task(db=db_session, task_id=task.id, task=task_update_clear)
    assert cleared_task is not None
    assert cleared_task.assigned_users == []


def test_start_task_records_started_by(db_session: Session) -> None:
    """start_task stores the started_by user ID on the task."""
    user_id = create_test_user(db_session, "test_start_task_records_started_by")
    task_in = TaskCreate(
        title="Test Task",
        description="Test Description",
        state="todo",
        created_by=user_id,
    )
    task = create_task(db=db_session, task=task_in)

    started = start_task(db=db_session, task=task, started_by_user_id=user_id)
    assert started.state == "in_progress"
    assert started.started_at is not None
    assert started.started_by == user_id


def test_start_task_without_user_started_by_is_none(db_session: Session) -> None:
    """start_task with no user ID leaves started_by as None."""
    user_id = create_test_user(db_session, "test_start_task_no_user")
    task_in = TaskCreate(
        title="Test Task",
        description="Test Description",
        state="todo",
        created_by=user_id,
    )
    task = create_task(db=db_session, task=task_in)

    started = start_task(db=db_session, task=task, started_by_user_id=None)
    assert started.started_by is None


def test_start_task_auto_assigns_user(db_session: Session) -> None:
    """start_task auto-assigns the starting user if not already in assigned_users."""
    user_id = create_test_user(db_session, "test_start_task_auto_assign")
    task_in = TaskCreate(
        title="Test Task",
        description="Test Description",
        state="todo",
        created_by=user_id,
    )
    task = create_task(db=db_session, task=task_in)
    assert task.assigned_users == []

    started = start_task(db=db_session, task=task, started_by_user_id=user_id)
    assert started.state == "in_progress"
    assert started.started_by == user_id
    assert any(u.id == user_id for u in started.assigned_users)


def test_start_task_does_not_duplicate_existing_assignee(db_session: Session) -> None:
    """start_task does not add user twice if already in assigned_users."""
    user_id = create_test_user(db_session, "test_start_task_no_dup")
    task_in = TaskCreate(
        title="Test Task",
        description="Already assigned",
        state="todo",
        created_by=user_id,
        assigned_user_ids=[user_id],
    )
    task = create_task(db=db_session, task=task_in)
    assert len(task.assigned_users) == 1

    started = start_task(db=db_session, task=task, started_by_user_id=user_id)
    assert len(started.assigned_users) == 1  # No duplicate


def test_reset_task_to_todo_clears_started_by(db_session: Session) -> None:
    """reset_task_to_todo clears started_by, started_at and completed_at."""
    user_id = create_test_user(db_session, "test_reset_task_clears_started_by")
    task_in = TaskCreate(
        title="Test Task",
        description="Test Description",
        state="todo",
        created_by=user_id,
    )
    task = create_task(db=db_session, task=task_in)

    started = start_task(db=db_session, task=task, started_by_user_id=user_id)
    assert started.started_by == user_id

    reset = reset_task_to_todo(db=db_session, task_id=task.id)
    assert reset.state == "todo"
    assert reset.started_at is None
    assert reset.completed_at is None
    assert reset.started_by is None


def test_reset_task_to_todo_from_done(db_session: Session) -> None:
    """reset_task_to_todo works on a completed task and clears all timestamps."""
    user_id = create_test_user(db_session, "test_reset_task_from_done")
    task_in = TaskCreate(
        title="Test Task",
        description="Test Description",
        state="todo",
        created_by=user_id,
    )
    task = create_task(db=db_session, task=task_in)

    start_task(db=db_session, task=task, started_by_user_id=user_id)
    complete_task(db=db_session, task=task)

    reset = reset_task_to_todo(db=db_session, task_id=task.id)
    assert reset.state == "todo"
    assert reset.started_at is None
    assert reset.completed_at is None
    assert reset.started_by is None


def test_reset_task_to_todo_nonexistent_raises(db_session: Session) -> None:
    """reset_task_to_todo raises TaskNotFoundError for missing task."""
    from taskmanagement_app.core.exceptions import TaskNotFoundError

    with pytest.raises(TaskNotFoundError):
        reset_task_to_todo(db=db_session, task_id=999999)
