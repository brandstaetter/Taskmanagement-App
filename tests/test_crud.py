from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from taskmanagement_app.crud.task import (
    complete_task,
    create_task,
    delete_task,
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
        due_date=(datetime.now() + timedelta(days=1)).date().isoformat(),
        state="todo",
    )
    task = create_task(db=db_session, task=task_in)
    assert task.title == task_in.title
    assert task.description == task_in.description
    assert task.state == task_in.state


def test_get_task(db_session: Session) -> None:
    task_in = TaskCreate(
        title="Test Task",
        description="Test Description",
        due_date=(datetime.now() + timedelta(days=1)).date().isoformat(),
        state="todo",
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
        due_date=(datetime.now() + timedelta(days=1)).date().isoformat(),
        state="todo",
    )
    task_in2 = TaskCreate(
        title="Test Task 2",
        description="Test Description 2",
        due_date=(datetime.now() + timedelta(days=2)).date().isoformat(),
        state="todo",
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
        due_date=(datetime.now() + timedelta(days=1)).date().isoformat(),
        state="todo",
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


def test_delete_task(db_session: Session) -> None:
    task_in = TaskCreate(
        title="Test Task",
        description="Test Description",
        due_date=(datetime.now() + timedelta(days=1)).date().isoformat(),
        state="todo",
    )
    task = create_task(db=db_session, task=task_in)
    deleted_task = delete_task(db=db_session, task_id=task.id)
    assert deleted_task
    assert deleted_task.id == task.id
    stored_task = get_task(db=db_session, task_id=task.id)
    assert stored_task is None


def test_task_state_transitions(db_session: Session) -> None:
    task_in = TaskCreate(
        title="Test Task",
        description="Test Description",
        due_date=(datetime.now() + timedelta(days=1)).date().isoformat(),
        state="todo",
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
