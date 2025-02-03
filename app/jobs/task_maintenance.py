import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.printing.printer_factory import PrinterFactory
from app.crud.task import delete_task, get_tasks, update_task
from app.db.models.task import TaskState
from app.db.session import SessionLocal

logger = logging.getLogger("app.jobs.task_maintenance")


def cleanup_old_tasks(db: Session) -> None:
    """Delete tasks that were completed more than 24 hours ago."""
    try:
        tasks = get_tasks(db)
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(hours=24)

        logger.info(f"Starting cleanup of old tasks. Current time: {now.isoformat()}")

        for task in tasks:
            if task.state == "done" and task.completed_at:
                completed_at = datetime.fromisoformat(
                    task.completed_at.replace("Z", "+00:00")
                )
                logger.debug(
                    f"Checking task {task.id} - completed at: {completed_at.isoformat()}"
                )

                if completed_at < cutoff:
                    logger.debug(
                        f"Deleting old completed task: {task.id} - {task.title}"
                    )
                    delete_task(db, task.id)

    except Exception as e:
        logger.error(f"Error cleaning up old tasks: {str(e)}", exc_info=True)


async def process_due_tasks(db: Session) -> None:
    """Print and start tasks that are due soon."""
    try:
        tasks = get_tasks(db)
        now = datetime.now(timezone.utc)
        soon = now + timedelta(hours=6)

        logger.info(
            f"Starting due task processing for {len(tasks)} tasks. "
            f"Current time: {now.isoformat()}, Looking up "
            f"to: {soon.isoformat()}"
        )

        # Create printer instance
        printer = PrinterFactory.create_printer()
        logger.debug(f"Created printer instance: {printer.__class__.__name__}")

        for task in tasks:
            try:
                if task.state == TaskState.todo and task.due_date:
                    due_date = datetime.fromisoformat(
                        task.due_date.replace("Z", "+00:00")
                    )
                    logger.debug(
                        f"Checking task {task.id} - "
                        f"due date: {due_date.isoformat()}, "
                        f"state: {task.state}"
                    )

                    # Check if task is due within 6 hours or overdue
                    if due_date <= soon:
                        logger.debug(f"Processing due task: {task.id} - {task.title}")

                        # Print task
                        await printer.print(task)
                        logger.debug(f"Printed task: {task.id}")

                        # Update task state
                        task_update = {
                            "state": TaskState.in_progress,
                            "started_at": now.isoformat(),
                        }
                        updated_task = update_task(db, task.id, task_update)
                        logger.debug(
                            f"Updated task state: {task.id} - new state: {updated_task.state}"
                        )
                    else:
                        logger.debug(
                            f"Task {task.id} not due yet. Due date: {due_date.isoformat()}"
                        )
                else:
                    logger.debug(
                        f"Skipping task {task.id} - state: {task.state}, due date: {task.due_date}"
                    )
            except Exception as e:
                logger.error(
                    f"Error processing task {task.id}: {str(e)}", exc_info=True
                )

    except Exception as e:
        logger.error(f"Error processing due tasks: {str(e)}", exc_info=True)


async def run_maintenance() -> None:
    """Run all maintenance tasks."""
    logger.info("Starting task maintenance job")

    db = SessionLocal()
    try:
        # Delete old completed tasks
        cleanup_old_tasks(db)

        # Process due tasks
        await process_due_tasks(db)

    except Exception as e:
        logger.error(f"Error in maintenance job: {str(e)}", exc_info=True)
    finally:
        db.close()

    logger.info("Completed task maintenance job")
