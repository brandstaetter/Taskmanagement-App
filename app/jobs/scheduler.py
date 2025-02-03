import logging
from datetime import datetime

from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from .task_maintenance import run_maintenance

logger = logging.getLogger("app.jobs.scheduler")

scheduler = AsyncIOScheduler()


def job_listener(event):
    """Log job execution status."""
    if event.exception:
        logger.error(f"Job {event.job_id} failed: {str(event.exception)}")
    else:
        logger.info(f"Job {event.job_id} completed successfully")


def setup_scheduler() -> None:
    """Setup the scheduler with all jobs."""
    try:
        # Add job execution listener
        scheduler.add_listener(job_listener, EVENT_JOB_EXECUTED | EVENT_JOB_ERROR)

        # Add task maintenance job to run every 15 minutes
        scheduler.add_job(
            run_maintenance,
            CronTrigger(minute="0,15,30,45"),  # Run at :00, :15, :30, :45
            id="task_maintenance",
            name="Task Maintenance",
            replace_existing=True,
            max_instances=1,  # Ensure only one instance runs at a time
            coalesce=True,  # Combine missed runs into a single run
            next_run_time=datetime.now(),  # Run immediately on startup
        )

        logger.info("Scheduled task maintenance job to run every 15 minutes")

    except Exception as e:
        logger.error(f"Error setting up scheduler: {str(e)}", exc_info=True)


def start_scheduler() -> None:
    """Start the scheduler."""
    try:
        setup_scheduler()
        scheduler.start()
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
        scheduler.shutdown()
        logger.info("Stopped scheduler")
    except Exception as e:
        logger.error(f"Error stopping scheduler: {str(e)}", exc_info=True)
