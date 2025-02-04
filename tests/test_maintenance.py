from datetime import datetime, timedelta, timezone
from typing import Literal
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.orm import Session

from taskmanagement_app.core.printing.base_printer import BasePrinter
from taskmanagement_app.crud.task import create_task, get_task
from taskmanagement_app.db.models.task import TaskModel
from taskmanagement_app.jobs.task_maintenance import (
    cleanup_old_tasks,
    process_due_tasks,
)
from taskmanagement_app.schemas.task import TaskCreate


def create_test_task(
    db: Session,
    *,
    title: str,
    state: Literal["todo", "in_progress", "done"],
    completed_at: str | None = None,
) -> TaskModel:
    task_in = TaskCreate(
        title=title,
        description="Test Description",
        due_date=(datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
        state=state,
    )
    task = create_task(db=db, task=task_in)
    if completed_at:
        task.completed_at = completed_at
        db.commit()
    return task


def test_cleanup_old_tasks(db_session: Session) -> None:
    """Test that old completed tasks are cleaned up."""
    # Create a task completed more than 24 hours ago
    old_task = create_test_task(
        db_session,
        title="Old Task",
        state="done",
        completed_at=(datetime.now(timezone.utc) - timedelta(hours=25)).isoformat(),
    )

    # Create a task completed less than 24 hours ago
    recent_task = create_test_task(
        db_session,
        title="Recent Task",
        state="done",
        completed_at=(datetime.now(timezone.utc) - timedelta(hours=23)).isoformat(),
    )

    # Create an incomplete task
    incomplete_task = create_test_task(
        db_session,
        title="Incomplete Task",
        state="todo",
    )

    # Run cleanup
    cleanup_old_tasks(db_session)

    # Verify old task was deleted
    assert get_task(db_session, old_task.id) is None

    # Verify recent task still exists
    assert get_task(db_session, recent_task.id) is not None

    # Verify incomplete task still exists
    assert get_task(db_session, incomplete_task.id) is not None


class MockPrinter(BasePrinter):
    """Mock printer for testing."""

    def __init__(self, config: dict = {}) -> None:
        """Initialize with config."""
        super().__init__(config=config)
        self._print = AsyncMock()

    @property
    def print(self):
        return self._print

    @print.setter
    def print(self, value):
        self._print = value


@pytest.mark.asyncio
async def test_process_due_tasks(db_session: Session) -> None:
    """Test that due tasks are processed correctly."""
    # Create a task due soon (within 6 hours)
    due_soon_task = create_test_task(
        db_session,
        title="Due Soon Task",
        state="todo",
    )
    due_soon_task.due_date = (
        datetime.now(timezone.utc) + timedelta(hours=3)
    ).isoformat()
    db_session.commit()

    # Create a task not due soon
    not_due_task = create_test_task(
        db_session,
        title="Not Due Task",
        state="todo",
    )
    not_due_task.due_date = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
    db_session.commit()

    # Create a task that's already in progress
    in_progress_task = create_test_task(
        db_session,
        title="In Progress Task",
        state="in_progress",
    )
    in_progress_task.due_date = (
        datetime.now(timezone.utc) + timedelta(hours=1)
    ).isoformat()
    db_session.commit()

    # Mock the printer
    mock_printer = MockPrinter()
    mock_printer.print = AsyncMock()

    with patch(
        "taskmanagement_app.jobs.task_maintenance.PrinterFactory.create_printer",
        return_value=mock_printer,
    ):
        # Run task processing
        await process_due_tasks(db_session)

        # Verify due soon task was processed
        updated_due_soon = get_task(db_session, due_soon_task.id)
        assert updated_due_soon is not None
        assert updated_due_soon.state == "in_progress"
        assert updated_due_soon.started_at is not None
        mock_printer.print.assert_called_once()

        # Verify not due task wasn't processed
        not_due = get_task(db_session, not_due_task.id)
        assert not_due is not None
        assert not_due.state == "todo"
        assert not_due.started_at is None

        # Verify in progress task wasn't processed again
        in_progress = get_task(db_session, in_progress_task.id)
        assert in_progress is not None
        assert in_progress.state == "in_progress"


@pytest.mark.asyncio
async def test_process_due_tasks_printer_error(db_session: Session) -> None:
    """Test that task processing handles printer errors gracefully."""
    # Create a task due soon
    due_soon_task = create_test_task(
        db_session,
        title="Due Soon Task",
        state="todo",
    )
    due_soon_task.due_date = (
        datetime.now(timezone.utc) + timedelta(hours=3)
    ).isoformat()
    db_session.commit()

    # Mock the printer with an error
    mock_printer = MockPrinter()
    mock_printer.print = AsyncMock(side_effect=Exception("Printer error"))

    with patch(
        "taskmanagement_app.jobs.task_maintenance.PrinterFactory.create_printer",
        return_value=mock_printer,
    ):
        # Run task processing
        await process_due_tasks(db_session)

        # Verify task wasn't updated due to printer error
        task = get_task(db_session, due_soon_task.id)
        assert task is not None
        assert task.state == "todo"
        assert task.started_at is None
        mock_printer.print.assert_called_once()
