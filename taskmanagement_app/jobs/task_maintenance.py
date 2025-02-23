"""Task maintenance jobs."""

import logging
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from taskmanagement_app.core.datetime_utils import ensure_timezone_aware, utc_now
from taskmanagement_app.core.printing.base_printer import BasePrinter
from taskmanagement_app.core.printing.printer_factory import PrinterFactory
from taskmanagement_app.crud.task import (
    archive_task,
    get_due_tasks,
    get_tasks,
    start_task,
)
from taskmanagement_app.db.models.task import TaskModel, TaskState

logger = logging.getLogger(__name__)


def cleanup_old_tasks(db: Session) -> None:
    """Archive tasks that were completed more than 7 days ago."""
    try:
        tasks = get_tasks(db, include_archived=False)
        now = utc_now()
        cutoff = now - timedelta(days=7)

        logger.info(f"Starting cleanup of old tasks. Current time: {now.isoformat()}")

        for task in tasks:
            # Refresh task from database to ensure it's attached to the session
            db.refresh(task)

            if task.state == TaskState.done and task.completed_at:
                # Ensure completed_at is timezone-aware
                completed_at = ensure_timezone_aware(task.completed_at)
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
        if task.state == TaskState.archived:
            logger.debug(f"Skipping archived task: {task.id} - {task.title}")
            return
        if task.due_date is None or ensure_timezone_aware(task.due_date) > soon:
            logger.debug(f"Skipping non-due task: {task.id} - {task.title}")
            return

        # Check if task is due within 6 hours or overdue
        if ensure_timezone_aware(task.due_date) <= soon:
            logger.debug(f"Processing due task: {task.id} - {task.title}")

            # Print task
            printer.print(task)
            logger.debug(f"Printed task: {task.id}")

            # Start the task
            updated_task = start_task(db, task)
            if updated_task:
                logger.debug(
                    f"Updated task state: {task.id} - "
                    f"new state: {updated_task.state}"
                )
            else:
                logger.error(f"Failed to update task {task.id}")
        else:
            logger.debug(
                f"Task {task.id} not due yet. " f"Due date: {task.due_date.isoformat()}"
            )
    except Exception as e:
        logger.error(f"Error processing due tasks: {str(e)}", exc_info=True)


def process_completed_tasks(db: Session) -> None:
    """Process completed tasks that are older than 7 days."""
    try:
        tasks = get_tasks(db, include_archived=False)  # Only get non-archived tasks
        now = utc_now()
        cutoff = now - timedelta(days=7)

        logger.info(
            f"Starting completed task processing. Current time: {now.isoformat()}"
        )

        for task in tasks:
            # Refresh task from database to ensure it's attached to the session
            db.refresh(task)

            if task.state == TaskState.done and task.completed_at:
                # Ensure completed_at is timezone-aware
                completed_at = ensure_timezone_aware(task.completed_at)
                logger.debug(
                    f"Checking task {task.id} - "
                    f"completed at: {completed_at.isoformat()}"
                )

                if completed_at < cutoff:
                    logger.info(f"Found old completed task: {task.id} - {task.title}")
                    # Archive old completed tasks
                    archive_task(db, task.id)

    except Exception as e:
        logger.error(f"Error processing completed tasks: {str(e)}", exc_info=True)


def process_due_tasks(db: Session) -> None:
    """Process tasks that are due or overdue."""
    try:
        now = utc_now()
        soon = now + timedelta(hours=6)  # Tasks due within 6 hours
        logger.info(f"Processing due tasks. Current time: {now.isoformat()}")

        # Get tasks that are due
        due_tasks = get_due_tasks(db)
        logger.info(f"Found {len(due_tasks)} due tasks")

        # Create printer instance
        printer = PrinterFactory.create_printer()

        # Process each due task
        for task in due_tasks:
            process_single_task(db, task, printer, now, soon)

    except Exception as e:
        logger.error(f"Error processing due tasks: {str(e)}", exc_info=True)


def run_maintenance() -> None:
    """Run all maintenance jobs."""
    logger.info("Starting maintenance jobs")
    try:
        from taskmanagement_app.db.session import SessionLocal

        db = SessionLocal()
        try:
            cleanup_old_tasks(db)
            process_completed_tasks(db)
            process_due_tasks(db)
            logger.info("Maintenance jobs completed successfully")
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Error running maintenance jobs: {str(e)}", exc_info=True)
