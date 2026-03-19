import logging
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from taskmanagement_app.core.printing.base_printer import BasePrinter
from taskmanagement_app.core.printing.printer_factory import PrinterFactory
from taskmanagement_app.crud.task import (
    archive_task,
    get_due_tasks,
    get_tasks,
    update_task,
)
from taskmanagement_app.db.models.task import TaskModel, TaskState

logger = logging.getLogger(__name__)


def cleanup_old_tasks(db: Session) -> None:
    """Delete tasks that were completed more than 24 hours ago."""
    try:
        tasks = get_tasks(db, include_archived=False)
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(hours=24)

        logger.info(f"Starting cleanup of old tasks. Current time: {now.isoformat()}")

        for task in tasks:
            # Refresh task from database to ensure it's attached to the session
            db.refresh(task)

            if task.state == TaskState.done and task.completed_at:
                try:
                    completed_at = datetime.fromisoformat(
                        task.completed_at.replace("Z", "+00:00")
                    )
                except (ValueError, TypeError):
                    logger.warning(
                        f"Invalid completed_at format for task {task.id}: "
                        f"{task.completed_at}. Removing completed_at."
                    )
                    task.completed_at = None
                    db.add(task)
                    db.commit()
                    continue

                logger.debug(
                    f"Checking task {task.id} - "
                    f"completed at: {completed_at.isoformat()}"
                )

                if completed_at < cutoff:
                    logger.debug(
                        f"Archiving old completed task: {task.id} - {task.title}"
                    )
                    archive_task(db, task.id)

    except Exception as e:
        logger.error(f"Error cleaning up old tasks: {str(e)}", exc_info=True)


def process_single_task(
    db: Session, task: TaskModel, printer: BasePrinter, now: datetime, soon: datetime
) -> None:
    """Process a single task that might be due.

    Args:
        db: Database session
        task: Task to process
        printer: Printer instance to use
        now: Current datetime
        soon: Datetime threshold for "due soon"
    """
    try:
        # Refresh task from database to ensure it's attached to the session
        db.refresh(task)

        # Parse due date
        try:
            due_date = datetime.fromisoformat(
                task.due_date.replace("Z", "+00:00") if task.due_date else ""
            )
        except (ValueError, TypeError):
            logger.warning(
                f"Invalid due_date format for task {task.id}: " f"{task.due_date}."
            )
            return

        # Check if task is due within 6 hours or overdue
        if due_date <= soon:
            logger.debug(f"Processing due task: {task.id} - {task.title}")

            # Print task
            printer.print(task)
            logger.debug(f"Printed task: {task.id}")

            # Update task state
            task_update = {
                "state": TaskState.in_progress,
                "started_at": now.isoformat(),
            }
            updated_task = update_task(db, task.id, task_update)
            if updated_task:
                logger.debug(
                    f"Updated task state: {task.id} - "
                    f"new state: {updated_task.state}"
                )
            else:
                logger.error(f"Failed to update task {task.id}")
        else:
            logger.debug(
                f"Task {task.id} not due yet. " f"Due date: {due_date.isoformat()}"
            )
    except Exception as e:
        logger.error(f"Error processing task {task.id}: {str(e)}", exc_info=True)


def process_completed_tasks(db: Session) -> None:
    """Process tasks that are marked as completed."""
    logger.info("Processing completed tasks")
    try:
        tasks = get_tasks(db, include_archived=False)  # Only get non-archived tasks
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(days=7)

        logger.info(
            f"Starting completed task processing. Current time: {now.isoformat()}"
        )

        for task in tasks:
            # Refresh task from database to ensure it's attached to the session
            db.refresh(task)

            if task.state == TaskState.done and task.completed_at:
                try:
                    completed_at = datetime.fromisoformat(
                        task.completed_at.replace("Z", "+00:00")
                    )
                except (ValueError, TypeError):
                    logger.warning(
                        f"Invalid completed_at format for task {task.id}: "
                        f"{task.completed_at}. Removing completed_at."
                    )
                    task.completed_at = None
                    db.add(task)
                    db.commit()
                    continue

                logger.debug(
                    f"Checking task {task.id} - "
                    f"completed at: {completed_at.isoformat()}"
                )

                if completed_at < cutoff:
                    logger.debug(
                        f"Archiving old completed task: {task.id} - {task.title}"
                    )
                    archive_task(db, task.id)

    except Exception as e:
        logger.error(f"Error processing completed tasks: {str(e)}", exc_info=True)


def process_due_tasks(db: Session) -> None:
    """Process tasks that are due or overdue."""
    logger.info("Processing due tasks")

    tasks = get_due_tasks(db)
    if not tasks:
        logger.debug("No due tasks found")
        return

    # Initialize printer
    try:
        printer = PrinterFactory.create_printer()
    except Exception as e:
        logger.error(f"Failed to initialize printer: {str(e)}")
        return

    # Get current time and soon threshold (6 hours from now)
    now = datetime.now(timezone.utc)
    soon = now + timedelta(hours=6)

    # Process each task
    for task in tasks:
        if task.due_date:
            # Refresh task from database to ensure it's attached to the session
            db.refresh(task)
            process_single_task(db, task, printer, now, soon)
        else:
            logger.debug(f"Skipping task {task.id} - no due date")


_LOCK_PATH = Path(tempfile.gettempdir()) / "taskman_maintenance.lock"


def _run_maintenance_inner() -> None:
    """Execute the actual maintenance work (no locking)."""
    from taskmanagement_app.db.session import SessionLocal

    db = SessionLocal()
    try:
        cleanup_old_tasks(db)
        process_completed_tasks(db)
        process_due_tasks(db)
    finally:
        db.close()


def _acquire_lock() -> Any:
    """Try to acquire an exclusive, non-blocking file lock.

    Returns the open file descriptor on success, or None if the lock is
    already held by another process (or on platforms without fcntl).
    """
    if sys.platform == "win32":
        # Windows runs a single uvicorn worker — no locking needed.
        # Return a sentinel so the caller knows to proceed.
        return True

    import fcntl  # type: ignore[unreachable]

    fd = None
    try:
        fd = open(_LOCK_PATH, "w")  # noqa: SIM115
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return fd
    except OSError:
        if fd is not None:
            fd.close()
        return None


def _release_lock(lock: Any) -> None:
    """Release the file lock acquired by _acquire_lock."""
    if lock is True or lock is None:
        return

    import fcntl  # noqa: F811

    try:
        fcntl.flock(lock, fcntl.LOCK_UN)  # type: ignore[attr-defined]
        lock.close()
    except OSError:
        pass


def run_maintenance() -> None:
    """Run all maintenance tasks.

    On Linux (gunicorn with multiple workers), uses a non-blocking file lock
    so only one worker executes the job. On Windows (single uvicorn), runs
    directly without locking.
    """
    lock = _acquire_lock()
    if lock is None:
        logger.debug("Maintenance job skipped — another worker holds the lock")
        return

    try:
        _run_maintenance_inner()
    except Exception as e:
        logger.error(f"Maintenance failed: {str(e)}", exc_info=True)
    finally:
        _release_lock(lock)
