"""Task scheduler module for running periodic maintenance tasks."""

import asyncio
import logging
from typing import Optional, Union

from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED, JobEvent  # type: ignore
from apscheduler.schedulers.asyncio import AsyncIOScheduler  # type: ignore
from apscheduler.triggers.cron import CronTrigger  # type: ignore

from taskmanagement_app.jobs.task_maintenance import run_maintenance

logger = logging.getLogger(__name__)


def job_listener(event: JobEvent) -> None:
    """Handle job execution events.
    
    Args:
        event: APScheduler job event
    """
    if event.code == EVENT_JOB_ERROR:
        logger.error("Job failed: %s", str(event.exception))
    elif event.code == EVENT_JOB_EXECUTED:
        logger.info("Job completed successfully: %s", event.job_id)


def get_scheduler() -> Optional[AsyncIOScheduler]:
    """Get the global scheduler instance."""
    try:
        _ = asyncio.get_event_loop()
        scheduler = AsyncIOScheduler()
        scheduler.start()
        return scheduler
    except Exception as e:
        logger.error(f"Failed to create scheduler: {e}", exc_info=True)
        return None


def setup_scheduler(scheduler: AsyncIOScheduler) -> None:
    """Setup the scheduler with all jobs."""
    try:
        # Add event listener for job execution
        scheduler.add_listener(job_listener, EVENT_JOB_ERROR | EVENT_JOB_EXECUTED)

        # Schedule maintenance job
        trigger = CronTrigger(hour="*")  # Run every hour
        scheduler.add_job(
            run_maintenance,
            trigger=trigger,
            id="maintenance_job",
            name="Task Maintenance",
            replace_existing=True,
        )

        logger.info("Scheduler setup completed")
    except Exception as e:
        logger.error(f"Error setting up scheduler: {str(e)}", exc_info=True)


def start_scheduler() -> None:
    """Start the scheduler."""
    scheduler = get_scheduler()
    if scheduler is not None:
        try:
            setup_scheduler(scheduler)
            logger.info("Started scheduler")

            # Log all scheduled jobs
            jobs = scheduler.get_jobs()
            for job in jobs:
                logger.info(f"Active job: {job.id} - Next run: {job.next_run_time}")

        except Exception as e:
            logger.error(f"Error starting scheduler: {str(e)}", exc_info=True)


def stop_scheduler() -> None:
    """Stop the scheduler."""
    try:
        scheduler = get_scheduler()
        if scheduler is not None:
            scheduler.shutdown()
            logger.info("Stopped scheduler")
    except Exception as e:
        logger.error(f"Error stopping scheduler: {str(e)}", exc_info=True)
