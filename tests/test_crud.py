from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from taskmanagement_app.crud.task import (
    archive_task,
    complete_task,
    create_task,
    get_due_tasks,
    get_task,
    get_tasks,
    start_task,
    update_task,
)
from taskmanagement_app.schemas.task import TaskCreate, TaskUpdate


def test_create_task(db_session: Session) -> None:
    task_in = TaskCreate(
        title="Test Task",
        description="Test Description",
        due_date=(datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
        state="todo",
        created_by=1,  # Add required created_by field
    )
    task = create_task(db=db_session, task=task_in)
    assert task.title == task_in.title
    assert task.description == task_in.description
    assert task.state == task_in.state


def test_get_task(db_session: Session) -> None:
    task_in = TaskCreate(
        title="Test Task",
        description="Test Description",
        due_date=(datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
        state="todo",
        created_by=1,
    )
    task = create_task(db=db_session, task=task_in)
    stored_task = get_task(db=db_session, task_id=task.id)
    assert stored_task
    assert task.id == stored_task.id
    assert task.title == stored_task.title
    assert task.description == stored_task.description


def test_get_tasks(db_session: Session) -> None:
    task_in1 = TaskCreate(
        title="Test Task 1",
        description="Test Description 1",
        due_date=(datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
        state="todo",
        created_by=1,
    )
    task_in2 = TaskCreate(
        title="Test Task 2",
        description="Test Description 2",
        due_date=(datetime.now(timezone.utc) + timedelta(days=2)).isoformat(),
        state="todo",
        created_by=1,
    )
    task1 = create_task(db=db_session, task=task_in1)
    task2 = create_task(db=db_session, task=task_in2)
    tasks = get_tasks(db=db_session)
    assert len(tasks) >= 2
    assert any(t.id == task1.id for t in tasks)
    assert any(t.id == task2.id for t in tasks)


def test_update_task(db_session: Session) -> None:
    task_in = TaskCreate(
        title="Test Task",
        description="Test Description",
        due_date=(datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
        state="todo",
        created_by=1,
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
    task_in = TaskCreate(
        title="Test Task",
        description="Test Description",
        due_date=(datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
        state="done",
        created_by=1,
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
    task_in = TaskCreate(
        title="Test Task",
        description="Test Description",
        due_date=(datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
        state="todo",
        created_by=1,
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
    # Create a task
    task_in = TaskCreate(
        title="Test Task",
        description="Test Description",
        due_date=(datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
        state="todo",
        created_by=1,
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
    # Create a task with invalid due date
    task_in = TaskCreate(
        title="Test Task",
        description="Test Description",
        state="todo",
        created_by=1,
    )
    task = create_task(db=db_session, task=task_in)
    task.due_date = "invalid-date"
    db_session.commit()

    # Test get_tasks still works
    tasks = get_tasks(db=db_session)
    assert any(t.id == task.id for t in tasks)

    # Test get_due_tasks handles invalid date
    from taskmanagement_app.crud.task import get_due_tasks

    due_tasks = get_due_tasks(db=db_session)
    assert not any(t.id == task.id for t in due_tasks)


def test_get_random_task(db_session: Session) -> None:
    """Test random task selection functionality."""
    from taskmanagement_app.crud.task import get_random_task

    # Create multiple tasks
    tasks = []
    for i in range(5):
        task_in = TaskCreate(
            title=f"Task {i}",
            description=f"Description {i}",
            due_date=(datetime.now(timezone.utc) + timedelta(days=i + 1)).isoformat(),
            state="todo",
            created_by=1,
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


def test_get_random_due_task(db_session: Session) -> None:
    """Test random due task selection functionality."""
    from taskmanagement_app.crud.task import get_random_task

    # Create tasks with different due dates
    tasks = []
    for i in range(5):
        task_in = TaskCreate(
            title=f"Task {i}",
            description=f"Description {i}",
            due_date=(datetime.now(timezone.utc) + timedelta(hours=i)).isoformat(),
            state="todo",
            created_by=1,
        )
        tasks.append(create_task(db=db_session, task=task_in))

    # Create a task due in far future
    future_task_in = TaskCreate(
        title="Future Task",
        description="Due in far future",
        due_date=(datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
        state="todo",
        created_by=1,
    )
    future_task = create_task(db=db_session, task=future_task_in)

    # Get random due task multiple times
    selected_ids = set()
    for _ in range(20):  # Try multiple times to get different tasks
        task = get_random_task(db=db_session)
        if task:
            selected_ids.add(task.id)
            # Verify we never get the future task
            assert task.id != future_task.id

    # Verify we got at least 2 different tasks
    assert len(selected_ids) >= 2
