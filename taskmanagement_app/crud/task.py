"""Task CRUD operations."""

import logging
import random
from datetime import timedelta, timezone
from typing import Any, Dict, List, Optional, Sequence, Union

from sqlalchemy.orm import Session

from taskmanagement_app.core.datetime_utils import ensure_timezone_aware, utc_now
from taskmanagement_app.core.exceptions import TaskNotFoundError, TaskStatusError
from taskmanagement_app.db.models.task import TaskModel, TaskState
from taskmanagement_app.schemas.task import TaskCreate, TaskUpdate

logger = logging.getLogger(__name__)


def ensure_task_datetime_aware(task: TaskModel) -> TaskModel:
    """Ensure all datetime fields in a task are timezone-aware."""
    if task.due_date:
        task.due_date = ensure_timezone_aware(task.due_date)
    if task.created_at:
        task.created_at = ensure_timezone_aware(task.created_at)
    if task.started_at:
        task.started_at = ensure_timezone_aware(task.started_at)
    if task.completed_at:
        task.completed_at = ensure_timezone_aware(task.completed_at)
    if task.updated_at:
        task.updated_at = ensure_timezone_aware(task.updated_at)
    return task


def get_tasks(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    include_archived: bool = False,
    state: Optional[str] = None,
) -> List[TaskModel]:
    """Get a list of tasks."""
    query = db.query(TaskModel)

    if not include_archived:
        query = query.filter(TaskModel.state != TaskState.archived)

    if state:
        query = query.filter(TaskModel.state == state)

    tasks = query.offset(skip).limit(limit).all()
    return [ensure_task_datetime_aware(task) for task in tasks]


def create_task(db: Session, task: TaskCreate) -> TaskModel:
    """Create a new task."""
    task_data = task.model_dump()

    # Ensure due_date is timezone-aware
    if task_data.get("due_date"):
        due_date = task_data["due_date"]
        if due_date.tzinfo is None:
            task_data["due_date"] = due_date.replace(tzinfo=timezone.utc)

    db_task = TaskModel(**task_data)
    db.add(db_task)
    db.commit()
    db.refresh(db_task)
    return ensure_task_datetime_aware(db_task)


def get_due_tasks(db: Session) -> List[TaskModel]:
    """Get all tasks that are due within the next 24 hours."""
    now = utc_now()
    tomorrow = now + timedelta(days=1)

    return (
        db.query(TaskModel)
        .filter(
            TaskModel.due_date <= tomorrow,
            TaskModel.due_date >= now,
            TaskModel.state != TaskState.archived,
            TaskModel.state != TaskState.done,
        )
        .all()
    )


def weighted_random_choice(  # noqa: C901
    tasks: Sequence[TaskModel],
) -> Optional[TaskModel]:
    """Choose a random task, weighted by due date and state."""
    if not tasks:
        return None

    now = utc_now()
    weights = []

    for task in tasks:
        if task.due_date is None:
            weights.append(1)  # Base weight for tasks without due date
            continue

        # Ensure task.due_date is timezone-aware and not None
        task = ensure_task_datetime_aware(task)
        assert task.due_date is not None  # for type checker
        hours_until_due = (task.due_date - now).total_seconds() / 3600
        days_until_due = hours_until_due / 24

        if hours_until_due < 0:
            weight = 100  # Overdue tasks
        elif hours_until_due < 24:
            weight = 80  # Due within 24 hours
        elif hours_until_due < 48:
            weight = 60  # Due within 2 days
        elif hours_until_due < 72:
            weight = 40  # Due within 3 days
        elif days_until_due <= 7:
            weight = 20  # Due within a week
        elif days_until_due <= 14:
            weight = 10  # Due within 2 weeks
        elif days_until_due <= 30:
            weight = 5  # Due within a month
        else:
            weight = 1  # Due beyond a month

        weights.append(weight)

    if not any(weights):
        return None

    return random.choices(tasks, weights=weights, k=1)[0]


def get_task(db: Session, task_id: int) -> TaskModel:
    """Get a task by its ID."""
    task = db.query(TaskModel).filter(TaskModel.id == task_id).first()
    if task is None:
        raise TaskNotFoundError(task_id)
    return ensure_task_datetime_aware(task)


def update_task(
    db: Session, task_id: int, task: Union[TaskUpdate, Dict[str, Any]]
) -> TaskModel:
    """Update a task with new values."""
    db_task = get_task(db, task_id)

    # Convert dict to TaskUpdate if needed
    if isinstance(task, dict):
        task = TaskUpdate(**task)

    # Update task fields
    task_data = task.model_dump(exclude_unset=True)

    # Ensure due_date is timezone-aware
    if "due_date" in task_data and task_data["due_date"] is not None:
        due_date = task_data["due_date"]
        if due_date.tzinfo is None:
            task_data["due_date"] = due_date.replace(tzinfo=timezone.utc)

    for field, value in task_data.items():
        setattr(db_task, field, value)

    db.commit()
    db.refresh(db_task)
    return ensure_task_datetime_aware(db_task)


def complete_task(db: Session, task: TaskModel) -> TaskModel:
    """Mark a task as completed and set the completion timestamp."""
    task.state = TaskState.done
    task.completed_at = utc_now()
    db.commit()
    db.refresh(task)
    return ensure_task_datetime_aware(task)


def start_task(db: Session, task: TaskModel) -> TaskModel:
    """Mark a task as in progress and set the start timestamp."""
    task.state = TaskState.in_progress
    task.started_at = utc_now()
    db.commit()
    db.refresh(task)
    return ensure_task_datetime_aware(task)


def archive_task(db: Session, task_id: int) -> TaskModel:
    """Archive a task by ID.

    Only tasks in 'todo' or 'done' state can be archived.
    Tasks in 'in_progress' state must be completed first.
    """
    task = get_task(db, task_id)

    if task.state == TaskState.archived:
        raise TaskStatusError(f"Task {task_id} is already archived")

    if task.state == TaskState.in_progress:
        raise TaskStatusError(
            f"Cannot archive task {task_id} in state '{task.state}'. "
            "Task must be completed first."
        )

    task.state = TaskState.archived
    db.commit()
    db.refresh(task)
    return ensure_task_datetime_aware(task)


def read_random_task(db: Session) -> Optional[TaskModel]:
    """Get a random task, prioritizing tasks that are:
    1. Not completed
    2. Due sooner
    3. Not yet started

    Uses weighted random selection where tasks due sooner have higher weights.
    Tasks due far in the future have a very low weight but can still be selected.
    """
    # Get all non-completed, non-archived tasks
    tasks = (
        db.query(TaskModel)
        .filter(
            TaskModel.state != TaskState.done,
            TaskModel.state != TaskState.archived,
        )
        .all()
    )

    if not tasks:
        return None

    # Use weighted random choice on all tasks
    task = weighted_random_choice(tasks)
    return ensure_task_datetime_aware(task) if task else None


def reset_task_to_todo(db: Session, task_id: int) -> TaskModel:
    """Reset a task to todo state and clear its progress timestamps."""
    task = get_task(db, task_id)
    task.state = TaskState.todo
    task.started_at = None
    task.completed_at = None
    db.commit()
    db.refresh(task)
    return ensure_task_datetime_aware(task)
