from datetime import datetime, timedelta, timezone
from typing import Literal
from unittest.mock import Mock, patch

from sqlalchemy.orm import Session

from taskmanagement_app.core.printing.base_printer import BasePrinter
from taskmanagement_app.crud.task import create_task, get_task
from taskmanagement_app.db.models.task import TaskModel, TaskState
from taskmanagement_app.jobs.task_maintenance import (
    cleanup_old_tasks,
    process_completed_tasks,
    process_due_tasks,
    run_maintenance,
)
from taskmanagement_app.schemas.task import TaskCreate


def create_test_task(
    db: Session,
    *,
    title: str,
    state: Literal["todo", "in_progress", "done", "archived"],
    completed_at: datetime | None = None,
) -> TaskModel:
    task_in = TaskCreate(
        title=title,
        description="Test Description",
        due_date=(datetime.now(timezone.utc) + timedelta(days=1)),
        state=state,
    )
    task = create_task(db=db, task=task_in)
    if completed_at:
        task.completed_at = completed_at
        db.commit()
    return task


def test_cleanup_old_tasks(db_session: Session) -> None:
    """Test that old completed tasks are archived."""
    # Create a task completed more than 24 hours ago
    old_task = create_test_task(
        db_session,
        title="Old Task",
        state="done",
        completed_at=(datetime.now(timezone.utc) - timedelta(hours=25)),
    )

    # Create a task completed less than 24 hours ago
    recent_task = create_test_task(
        db_session,
        title="Recent Task",
        state="done",
        completed_at=(datetime.now(timezone.utc) - timedelta(hours=23)),
    )

    # Create an incomplete task
    incomplete_task = create_test_task(
        db_session,
        title="Incomplete Task",
        state="todo",
    )

    # Create an already archived task
    already_archived = create_test_task(
        db_session,
        title="Already Archived Task",
        state="archived",
        completed_at=(datetime.now(timezone.utc) - timedelta(hours=30)),
    )

    # Run cleanup
    cleanup_old_tasks(db_session)

    # Verify old task was archived
    old_task_check = get_task(db_session, old_task.id)
    assert old_task_check is not None
    assert old_task_check.state == "archived"

    # Verify recent task still exists and is not archived
    recent_task_check = get_task(db_session, recent_task.id)
    assert recent_task_check is not None
    assert recent_task_check.state == "done"

    # Verify incomplete task still exists and is not archived
    incomplete_task_check = get_task(db_session, incomplete_task.id)
    assert incomplete_task_check is not None
    assert incomplete_task_check.state == "todo"

    # Verify already archived task remains archived
    archived_task = get_task(db_session, already_archived.id)
    assert archived_task is not None
    assert archived_task.state == "archived"


class MockPrinter(BasePrinter):
    """Mock printer for testing."""

    def __init__(self, config: dict = {}) -> None:
        """Initialize with config."""
        super().__init__(config=config)
        self._print = Mock()

    @property
    def print(self):
        return self._print

    @print.setter
    def print(self, value):
        self._print = value


def test_process_due_tasks(db_session: Session) -> None:
    """Test that due tasks are processed correctly."""
    # Create a task due soon (within 6 hours)
    due_soon_task = create_test_task(
        db_session,
        title="Due Soon Task",
        state="todo",
    )
    due_soon_task.due_date = datetime.now(timezone.utc) + timedelta(hours=3)
    db_session.commit()

    # Create a task not due soon
    not_due_task = create_test_task(
        db_session,
        title="Not Due Task",
        state="todo",
    )
    not_due_task.due_date = datetime.now(timezone.utc) + timedelta(days=2)
    db_session.commit()

    # Create a task that's already in progress
    in_progress_task = create_test_task(
        db_session,
        title="In Progress Task",
        state="in_progress",
    )
    in_progress_task.due_date = datetime.now(timezone.utc) + timedelta(hours=1)
    db_session.commit()

    # Create an archived task that's due soon
    archived_task = create_test_task(
        db_session,
        title="Archived Task",
        state="archived",
    )
    archived_task.due_date = datetime.now(timezone.utc) + timedelta(hours=2)
    db_session.commit()

    # Mock the printer
    mock_printer = MockPrinter()
    mock_printer.print = Mock()

    with patch(
        "taskmanagement_app.jobs.task_maintenance.PrinterFactory.create_printer",
        return_value=mock_printer,
    ):
        # Run task processing
        process_due_tasks(db_session)

        # Verify due soon task was processed
        updated_due_soon = get_task(db_session, due_soon_task.id)
        assert updated_due_soon is not None
        assert updated_due_soon.state == TaskState.in_progress
        assert updated_due_soon.started_at is not None
        mock_printer.print.assert_called()

        # Verify not due task wasn't processed
        not_due = get_task(db_session, not_due_task.id)
        assert not_due is not None
        assert not_due.state == "todo"
        assert not_due.started_at is None

        # Verify in progress task wasn't processed again
        in_progress = get_task(db_session, in_progress_task.id)
        assert in_progress is not None
        assert in_progress.state == TaskState.in_progress

        # Verify archived task wasn't processed
        archived = get_task(db_session, archived_task.id)
        assert archived is not None
        assert archived.state == "archived"
        assert archived.started_at is None


def test_process_due_tasks_printer_error(db_session: Session) -> None:
    """Test that task processing handles printer errors gracefully."""
    # Create a task due soon (within 6 hours)
    due_soon_task = create_test_task(
        db_session,
        title="Due Soon Task",
        state="todo",
    )
    due_soon_task.due_date = datetime.now(timezone.utc) + timedelta(hours=3)
    db_session.commit()

    # Create an archived task that's due soon
    archived_task = create_test_task(
        db_session,
        title="Archived Task",
        state="archived",
    )
    archived_task.due_date = datetime.now(timezone.utc) + timedelta(hours=2)
    db_session.commit()

    # Mock the printer to raise an error
    mock_printer = MockPrinter()
    mock_printer.print = Mock(side_effect=Exception("Printer error"))

    with patch(
        "taskmanagement_app.jobs.task_maintenance.PrinterFactory.create_printer",
        return_value=mock_printer,
    ):
        # Run task processing
        process_due_tasks(db_session)

        # Verify task state wasn't changed despite printer error
        task = get_task(db_session, due_soon_task.id)
        assert task is not None
        assert task.state == "todo"
        assert task.started_at is None
        mock_printer.print.assert_called()

        # Verify archived task wasn't processed
        archived = get_task(db_session, archived_task.id)
        assert archived is not None
        assert archived.state == "archived"
        assert archived.started_at is None


def test_process_completed_tasks(db_session: Session) -> None:
    """Test that completed tasks are archived after 7 days."""
    # Create a task completed more than 7 days ago
    old_completed = create_test_task(
        db_session,
        title="Old Completed Task",
        state="done",
        completed_at=(datetime.now(timezone.utc) - timedelta(days=8)),
    )

    # Create a task completed less than 7 days ago
    recent_completed = create_test_task(
        db_session,
        title="Recent Completed Task",
        state="done",
        completed_at=(datetime.now(timezone.utc) - timedelta(days=3)),
    )

    # Create an in-progress task
    in_progress = create_test_task(
        db_session,
        title="In Progress Task",
        state="in_progress",
    )

    # Create an already archived task
    already_archived = create_test_task(
        db_session,
        title="Already Archived Task",
        state="archived",
        completed_at=(datetime.now(timezone.utc) - timedelta(days=10)),
    )

    # Store task IDs for later verification
    old_completed_id = old_completed.id
    recent_completed_id = recent_completed.id
    in_progress_id = in_progress.id
    already_archived_id = already_archived.id

    # Run maintenance
    process_completed_tasks(db_session)

    # Verify old completed task was archived
    old_task = get_task(db_session, old_completed_id)
    assert old_task is not None
    assert old_task.state == "archived"

    # Verify recent completed task was not archived
    recent_task = get_task(db_session, recent_completed_id)
    assert recent_task is not None
    assert recent_task.state == "done"

    # Verify in-progress task was not affected
    active_task = get_task(db_session, in_progress_id)
    assert active_task is not None
    assert active_task.state == TaskState.in_progress

    # Verify already archived task remains archived
    archived_task = get_task(db_session, already_archived_id)
    assert archived_task is not None
    assert archived_task.state == TaskState.archived


def test_process_due_tasks_printer_initialization_error(
    db_session: Session,
) -> None:
    """Test that task processing handles printer initialization errors gracefully."""
    # Create a task due soon (within 6 hours)
    due_soon_task = create_test_task(
        db_session,
        title="Due Soon Task",
        state="todo",
    )
    due_soon_task.due_date = datetime.now(timezone.utc) + timedelta(hours=3)
    db_session.commit()

    # Create an archived task that's due soon
    archived_task = create_test_task(
        db_session,
        title="Archived Task",
        state="archived",
    )
    archived_task.due_date = datetime.now(timezone.utc) + timedelta(hours=2)
    db_session.commit()

    # Mock printer factory to raise an error
    with patch(
        "taskmanagement_app.jobs.task_maintenance.PrinterFactory.create_printer",
        side_effect=Exception("Printer initialization error"),
    ):
        # Run task processing
        process_due_tasks(db_session)

        # Verify task wasn't processed due to printer error
        task = get_task(db_session, due_soon_task.id)
        assert task is not None
        assert task.state == "todo"
        assert task.started_at is None

        # Verify archived task wasn't processed
        archived = get_task(db_session, archived_task.id)
        assert archived is not None
        assert archived.state == "archived"
        assert archived.started_at is None


def test_run_maintenance(db_session: Session) -> None:
    """Test the complete maintenance workflow.

    This test creates an old completed task and a task that is due soon, and
    verifies that the old completed task is archived and the due task is
    processed and printed.
    """
    # Create various tasks
    old_completed = create_test_task(
        db_session,
        title="Old Completed Task",
        state="done",
        completed_at=(datetime.now(timezone.utc) - timedelta(days=8)),
    )

    due_soon = create_test_task(
        db_session,
        title="Due Soon Task",
        state="todo",
    )
    due_soon.due_date = datetime.now(timezone.utc) + timedelta(hours=3)
    db_session.commit()

    # Store task IDs for later verification
    old_completed_id = old_completed.id
    due_soon_id = due_soon.id

    # Mock the printer
    mock_printer = MockPrinter()
    mock_printer.print = Mock()

    class TestSessionLocal:
        def __init__(self, session: Session):
            self.session = session

        def __call__(self):
            return self.session

    with (
        patch(
            "taskmanagement_app.jobs.task_maintenance.PrinterFactory.create_printer",
            return_value=mock_printer,
        ),
        patch(
            "taskmanagement_app.db.session.SessionLocal",
            TestSessionLocal(db_session),
        ),
    ):
        # Run maintenance
        run_maintenance()

        # Verify old completed task was archived
        old_task = get_task(db_session, old_completed_id)
        assert old_task is not None
        assert old_task.state == "archived"

        # Verify due task was processed
        due_task = get_task(db_session, due_soon_id)
        assert due_task is not None
        assert due_task.state == TaskState.in_progress
        assert due_task.started_at is not None
        mock_printer.print.assert_called()
